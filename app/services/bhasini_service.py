import os
import json
import base64
import logging
import hashlib
import requests
from flask import current_app

logger = logging.getLogger(__name__)

class BhasiniService:
    """
    Bhashini (National Language Translation Mission - ULCA / Dhruva) API Service.
    Provides ASR (Speech-to-Text), NMT (Translation), and TTS (Text-to-Speech)
    for Indian languages (Marathi 'mr', Hindi 'hi', English 'en', etc.).
    """
    
    PIPELINE_CONFIG_URL = "https://meity-auth.bhashini.gov.in/ulca/apis/v0/model/getModelsPipeline"
    INFERENCE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
    
    # In-memory cache for pipeline compute configs to minimize pipeline lookup latency
    _pipeline_cache = {}

    @classmethod
    def get_credentials(cls):
        try:
            cfg = current_app.config
        except Exception:
            cfg = {}

        user_id = cfg.get("BHASHINI_USER_ID") or os.environ.get("BHASHINI_USER_ID") or os.environ.get("BHASINI_USER_ID", "")
        api_key = cfg.get("BHASHINI_API_KEY") or os.environ.get("BHASINI_UDYAT_API") or os.environ.get("BHASHINI_API_KEY") or os.environ.get("BHASINI_API_KEY", "")
        pipeline_id = cfg.get("BHASHINI_PIPELINE_ID") or os.environ.get("BHASHINI_PIPELINE_ID") or os.environ.get("BHASINI_PIPELINE_ID") or "64392f96daac500b55c543d5"
        inference_key = cfg.get("BHASHINI_INFERENCE_API_KEY") or os.environ.get("BHASINI_INFERENCE_KEY") or os.environ.get("BHASHINI_INFERENCE_API_KEY") or os.environ.get("BHASINI_INFERENCE_API_KEY", "")
        return {
            "user_id": user_id,
            "api_key": api_key,
            "pipeline_id": pipeline_id,
            "inference_key": inference_key
        }

    @classmethod
    def is_configured(cls):
        creds = cls.get_credentials()
        return bool((creds["user_id"] and creds["api_key"]) or creds["inference_key"])

    @classmethod
    def get_pipeline_config(cls, task_type="asr", source_lang="mr", target_lang=None):
        """
        Fetches dynamic service IDs and callback endpoints for a given Bhashini task.
        """
        creds = cls.get_credentials()
        cache_key = f"{task_type}_{source_lang}_{target_lang or ''}"
        if cache_key in cls._pipeline_cache:
            return cls._pipeline_cache[cache_key]

        if not (creds["user_id"] and creds["api_key"]):
            logger.warning("Bhashini user_id or api_key missing.")
            return None

        task_config = {
            "taskType": task_type,
            "config": {
                "language": {
                    "sourceLanguage": source_lang
                }
            }
        }
        if target_lang and task_type == "translation":
            task_config["config"]["language"]["targetLanguage"] = target_lang

        payload = {
            "pipelineTasks": [task_config],
            "pipelineRequestConfig": {
                "pipelineId": creds["pipeline_id"] or "64392f96daac500b55c543d5"
            }
        }

        headers = {
            "userID": creds["user_id"],
            "ulcaApiKey": creds["api_key"],
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(cls.PIPELINE_CONFIG_URL, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                cls._pipeline_cache[cache_key] = data
                return data
            else:
                logger.error(f"Bhashini pipeline config error: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Failed to fetch Bhashini pipeline config: {e}")
        return None

    @classmethod
    def speech_to_text(cls, audio_base64: str, source_lang: str = "mr") -> dict:
        """
        Converts base64 encoded audio (WAV/MP3/WEBM/FLAC) to text using Bhashini ASR.
        """
        # Clean potential data URI header
        if "," in audio_base64:
            audio_base64 = audio_base64.split(",", 1)[1]

        creds = cls.get_credentials()
        
        # If API is configured, call Bhashini Inference endpoint
        if cls.is_configured():
            try:
                pipeline_data = cls.get_pipeline_config(task_type="asr", source_lang=source_lang)
                service_id = None
                inference_key = creds["inference_key"]
                endpoint_url = cls.INFERENCE_URL

                if pipeline_data:
                    pipeline_tasks = pipeline_data.get("pipelineResponseConfig", [])
                    if pipeline_tasks:
                        service_id = pipeline_tasks[0].get("config", [{}])[0].get("serviceId")
                    inference_auth = pipeline_data.get("pipelineInferenceAPIEndPoint", {})
                    if inference_auth:
                        endpoint_url = inference_auth.get("callbackUrl", cls.INFERENCE_URL)
                        inference_key = inference_auth.get("inferenceApiKey", {}).get("value", inference_key)

                payload = {
                    "pipelineTasks": [
                        {
                            "taskType": "asr",
                            "config": {
                                "language": {
                                    "sourceLanguage": source_lang
                                },
                                "serviceId": service_id or f"ai4bharat/conformer-asr-{source_lang}-gpu",
                                "audioFormat": "wav",
                                "samplingRate": 16000
                            }
                        }
                    ],
                    "inputData": {
                        "audio": [
                            {
                                "audioContent": audio_base64
                            }
                        ]
                    }
                }

                headers = {
                    "Authorization": inference_key or creds["api_key"],
                    "Content-Type": "application/json"
                }

                resp = requests.post(endpoint_url, json=payload, headers=headers, timeout=20)
                if resp.status_code == 200:
                    resp_json = resp.json()
                    pipeline_out = resp_json.get("pipelineResponse", [])
                    if pipeline_out:
                        output_arr = pipeline_out[0].get("output", [])
                        if output_arr:
                            transcript = output_arr[0].get("source", "")
                            return {"success": True, "text": transcript, "provider": "bhashini"}
                else:
                    logger.warning(f"Bhashini ASR call returned {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Bhashini ASR error: {e}")

        # Fallback / Mock when keys pending or network unavailable
        return {
            "success": False,
            "error": "Bhashini ASR credentials pending or service unreachable",
            "fallback_available": True
        }

    @classmethod
    def text_to_speech(cls, text: str, source_lang: str = "mr", gender: str = "female") -> dict:
        """
        Converts text to speech audio using Bhashini TTS. Returns base64 encoded audio.
        """
        if not text or not text.strip():
            return {"success": False, "error": "Empty text for TTS"}

        creds = cls.get_credentials()
        
        if cls.is_configured():
            try:
                pipeline_data = cls.get_pipeline_config(task_type="tts", source_lang=source_lang)
                service_id = None
                inference_key = creds["inference_key"]
                endpoint_url = cls.INFERENCE_URL

                if pipeline_data:
                    pipeline_tasks = pipeline_data.get("pipelineResponseConfig", [])
                    if pipeline_tasks:
                        service_id = pipeline_tasks[0].get("config", [{}])[0].get("serviceId")
                    inference_auth = pipeline_data.get("pipelineInferenceAPIEndPoint", {})
                    if inference_auth:
                        endpoint_url = inference_auth.get("callbackUrl", cls.INFERENCE_URL)
                        inference_key = inference_auth.get("inferenceApiKey", {}).get("value", inference_key)

                payload = {
                    "pipelineTasks": [
                        {
                            "taskType": "tts",
                            "config": {
                                "language": {
                                    "sourceLanguage": source_lang
                                },
                                "serviceId": service_id or f"ai4bharat/indic-tts-{source_lang}",
                                "gender": gender
                            }
                        }
                    ],
                    "inputData": {
                        "input": [
                            {
                                "source": text[:800] # Limit chunk length for TTS stability
                            }
                        ]
                    }
                }

                headers = {
                    "Authorization": inference_key or creds["api_key"],
                    "Content-Type": "application/json"
                }

                resp = requests.post(endpoint_url, json=payload, headers=headers, timeout=20)
                if resp.status_code == 200:
                    resp_json = resp.json()
                    pipeline_out = resp_json.get("pipelineResponse", [])
                    if pipeline_out:
                        audio_arr = pipeline_out[0].get("audio", [])
                        if audio_arr:
                            audio_b64 = audio_arr[0].get("audioContent", "")
                            return {"success": True, "audio_base64": audio_b64, "provider": "bhashini", "format": "wav"}
                else:
                    logger.warning(f"Bhashini TTS call returned {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Bhashini TTS error: {e}")

        return {
            "success": False,
            "error": "Bhashini TTS credentials pending or service unreachable",
            "fallback_available": True
        }

    @classmethod
    def translate_text(cls, text: str, source_lang: str = "mr", target_lang: str = "en") -> dict:
        """
        Translates text between Indian languages and English using Bhashini NMT.
        """
        if not text or not text.strip():
            return {"success": False, "error": "Empty text for translation"}

        creds = cls.get_credentials()
        
        if cls.is_configured():
            try:
                pipeline_data = cls.get_pipeline_config(task_type="translation", source_lang=source_lang, target_lang=target_lang)
                service_id = None
                inference_key = creds["inference_key"]
                endpoint_url = cls.INFERENCE_URL

                if pipeline_data:
                    pipeline_tasks = pipeline_data.get("pipelineResponseConfig", [])
                    if pipeline_tasks:
                        service_id = pipeline_tasks[0].get("config", [{}])[0].get("serviceId")
                    inference_auth = pipeline_data.get("pipelineInferenceAPIEndPoint", {})
                    if inference_auth:
                        endpoint_url = inference_auth.get("callbackUrl", cls.INFERENCE_URL)
                        inference_key = inference_auth.get("inferenceApiKey", {}).get("value", inference_key)

                payload = {
                    "pipelineTasks": [
                        {
                            "taskType": "translation",
                            "config": {
                                "language": {
                                    "sourceLanguage": source_lang,
                                    "targetLanguage": target_lang
                                },
                                "serviceId": service_id or f"ai4bharat/indictrans-v2-all-gpu"
                            }
                        }
                    ],
                    "inputData": {
                        "input": [
                            {
                                "source": text
                            }
                        ]
                    }
                }

                headers = {
                    "Authorization": inference_key or creds["api_key"],
                    "Content-Type": "application/json"
                }

                resp = requests.post(endpoint_url, json=payload, headers=headers, timeout=15)
                if resp.status_code == 200:
                    resp_json = resp.json()
                    pipeline_out = resp_json.get("pipelineResponse", [])
                    if pipeline_out:
                        out_arr = pipeline_out[0].get("output", [])
                        if out_arr:
                            translated_text = out_arr[0].get("target", "")
                            return {"success": True, "translated_text": translated_text, "provider": "bhashini"}
                else:
                    logger.warning(f"Bhashini translation returned {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Bhashini translation error: {e}")

        return {
            "success": False,
            "error": "Bhashini translation unavailable",
            "fallback_available": True
        }

    @classmethod
    def translate_cached(cls, text: str, source_lang: str = "en", target_lang: str = "mr") -> str:
        """
        Translate text with Flask-Cache. Returns translated string or original text as fallback.
        Cache key is a hash of (text, source_lang, target_lang) — 24h TTL by default.
        
        Usage:
            from app.services.bhasini_service import BhasiniService
            mr_text = BhasiniService.translate_cached(advisory_text, source_lang='en', target_lang='mr')
        """
        if not text or not text.strip():
            return text

        try:
            from app import cache
            text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
            cache_key = f"bhasini_nmt_{source_lang}_{target_lang}_{text_hash}"
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Cache HIT: {cache_key[:50]}")
                return cached

            result = cls.translate_text(text, source_lang=source_lang, target_lang=target_lang)
            if result.get("success"):
                translated = result["translated_text"]
                cache.set(cache_key, translated, timeout=86400)
                logger.debug(f"Cache SET (Bhashini): {cache_key[:50]}")
                return translated

            logger.info(f"Bhashini unavailable ({result.get('error')}), engaging Gemini AI translation fallback...")
            try:
                from app.services.gemini_service import GeminiService
                gemini_translated = GeminiService.translate_text(text, target_lang=target_lang)
                if gemini_translated:
                    cache.set(cache_key, gemini_translated, timeout=86400)
                    logger.debug(f"Cache SET (Gemini fallback): {cache_key[:50]}")
                    return gemini_translated
            except Exception as ge:
                logger.warning(f"Gemini translation fallback error: {ge}")

            return text
        except Exception as e:
            logger.error(f"translate_cached error: {e}")
            return text
