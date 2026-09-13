import os
from google import genai
from google.genai import types
from flask import current_app

from .rag_service import RAGService


class GeminiService:
    @staticmethod
    def ask_assistant(message, history=None, language="mr"):
        """
        Send a message to the Gemini Agricultural Assistant.

        In DEMO_MODE, returns a mock response when no valid API key
        is configured. Supports Marathi ('mr'), Hindi ('hi'), and English ('en').
        """

        api_key = current_app.config.get("GEMINI_API_KEY")
        demo_mode = current_app.config.get("DEMO_MODE", True)

        # Language label map
        lang_names = {
            "mr": "मराठी (Marathi)",
            "hi": "हिंदी (Hindi)",
            "en": "English"
        }
        target_lang_name = lang_names.get(language, "मराठी (Marathi)")

        # ---------------------------------------------------------
        # DEMO MODE / API KEY CHECK
        # ---------------------------------------------------------
        if not api_key or api_key == "your_gemini_api_key_here":
            if demo_mode:
                if language == "mr":
                    demo_text = (
                        f"मी PikDrishti AI व्हॉइस असिस्टंट आहे. "
                        f"तुमचा प्रश्न: '{message}'\n\n"
                        "Google Gemini व भाषिणी AI द्वारे अचूक कृषी सल्ला मिळवण्यासाठी API Key कॉन्फिगर करा."
                    )
                else:
                    demo_text = (
                        "मैं PikDrishti AI Demo Assistant हूँ। "
                        f"आपने पूछा: '{message}'।\n\n"
                        "Production environment में Google Gemini का "
                        "expert agricultural response प्राप्त करने के लिए "
                        "GEMINI_API_KEY configure करें।"
                    )
                return {
                    "success": True,
                    "response": demo_text,
                }

            return {
                "success": False,
                "error": "Gemini API key is not configured.",
            }

        try:
            # -----------------------------------------------------
            # GEMINI CLIENT
            # -----------------------------------------------------
            client = genai.Client(api_key=api_key)

            model_name = current_app.config.get(
                "GEMINI_MODEL",
                "gemini-2.5-flash",
            )

            # -----------------------------------------------------
            # RAG CONTEXT
            # -----------------------------------------------------
            rag_context = RAGService.search(message)

            # -----------------------------------------------------
            # SYSTEM INSTRUCTION
            # -----------------------------------------------------
            system_instruction = f"""
You are PikDrishti AI (AgriVision), an expert agricultural assistant designed specifically for farmers.

Your Core Purpose:
- Diagnose crop diseases and explain symptoms clearly
- Provide immediate, actionable treatment recommendations (chemical and organic)
- Give pest management, fertilizer, and irrigation guidance
- Promote safe, sustainable farming best practices
- Assist farmers in Maharashtra and across India in their native language

CRITICAL LANGUAGE RULE:
- You MUST reply entirely in {target_lang_name}.
- Keep technical agricultural/scientific terms alongside simple vernacular explanations.
- Keep tone respectful, encouraging, and farmer-friendly.
- Keep responses structured, concise, and optimized for mobile screens and voice playback.

FORMAT THE RESPONSE FOR A MOBILE CHAT & VOICE UI:
- Use ### for major sections.
- Use **bold** for key concepts, chemical names, dosage, or labels.
- Use bullet lists for remedies and points.
- Use numbered lists for step-by-step procedures.
- Keep sentences clean and natural so they sound great when read aloud via Text-to-Speech.
- Do not output raw JSON or code blocks unless explicitly requested.
"""

            # -----------------------------------------------------
            # ADD RAG CONTEXT
            # -----------------------------------------------------
            if rag_context:
                system_instruction += f"""

स्थानीय कृषि संदर्भ:

नीचे दिए गए स्थानीय agricultural policies और guidelines
का उपयोग केवल तभी करें जब वे user के प्रश्न से संबंधित हों:

--- BEGIN LOCAL CONTEXT ---
{rag_context}
--- END LOCAL CONTEXT ---
"""

            # -----------------------------------------------------
            # CONVERT DATABASE HISTORY TO GEMINI HISTORY
            # -----------------------------------------------------
            gemini_history = []

            if history:
                # Gemini requires history to start with 'user' role
                # If initial message is an AI context card, append to system instruction
                msg_list = list(history)
                while msg_list and msg_list[0].role != "user":
                    context_msg = msg_list.pop(0)
                    system_instruction += f"\n\n--- संदर्भ / CONTEXT FROM DIAGNOSIS ---\n{context_msg.content}\n---------------------------------------\n"

                for msg in msg_list:
                    role = "user" if msg.role == "user" else "model"
                    if gemini_history and gemini_history[-1].role == role:
                        gemini_history[-1].parts[0].text += f"\n\n{msg.content}"
                    else:
                        gemini_history.append(
                            types.Content(
                                role=role,
                                parts=[
                                    types.Part.from_text(
                                        text=msg.content
                                    )
                                ],
                            )
                        )

            # -----------------------------------------------------
            # CREATE CHAT
            # -----------------------------------------------------
            chat = client.chats.create(
                model=model_name,
                history=gemini_history,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )

            # -----------------------------------------------------
            # SEND USER MESSAGE
            # -----------------------------------------------------
            response = chat.send_message(
                message=message
            )

            # -----------------------------------------------------
            # RESPONSE
            # -----------------------------------------------------
            return {
                "success": True,
                "response": response.text,
            }

        except Exception as e:
            current_app.logger.exception(
                "Gemini assistant error"
            )

            return {
                "success": False,
                "error": str(e),
            }

    @classmethod
    def translate_text(cls, text: str, target_lang: str = "mr") -> str:
        """
        Translates text to target Indian language (e.g. Marathi or Hindi) using Gemini.
        """
        if not text or not text.strip():
            return ""

        api_key = None
        try:
            api_key = current_app.config.get("GEMINI_API_KEY")
        except Exception:
            pass
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
            return ""

        model_name = "gemini-3.6-flash"
        try:
            model_name = current_app.config.get("GEMINI_MODEL") or model_name
        except Exception:
            pass
        model_name = os.environ.get("GEMINI_MODEL") or model_name

        lang_name = "मराठी (Marathi)" if target_lang == "mr" else ("हिंदी (Hindi)" if target_lang == "hi" else "English")

        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                f"You are a professional agricultural translator.\n"
                f"Translate the following agricultural text accurately into natural, clear {lang_name}.\n"
                f"Output ONLY the translated text, with no explanations, greetings, quotes, or markdown code blocks.\n\n"
                f"Text to translate:\n{text}"
            )
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception as e:
            try:
                current_app.logger.warning(f"Gemini translation fallback error: {e}")
            except Exception:
                pass
        return ""

