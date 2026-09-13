translation_js = """

<script>
// Bhashini Cached Translation - Disease Result Page
const _drOriginals = {};
async function _translateEl(el, lang) {
    if (!el) return;
    const key = el.dataset.trKey || el.id;
    if (!key) return;
    if (!_drOriginals[key]) _drOriginals[key] = el.innerText.trim();
    const original = _drOriginals[key];
    if (lang === 'en') { el.innerText = original; return; }
    try {
        const r = await fetch('/api/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: original, source_lang: 'en', target_lang: 'mr' })
        });
        const d = await r.json();
        if (d.success && d.translated_text) el.innerText = d.translated_text;
    } catch(e) {}
}
async function applyResultLanguage(lang) {
    const els = document.querySelectorAll('[data-tr="dynamic"]');
    for (const el of els) await _translateEl(el, lang);
}
document.addEventListener('DOMContentLoaded', function() {
    const lang = localStorage.getItem('pikdrishti_lang') || 'mr';
    if (lang === 'mr') setTimeout(() => applyResultLanguage('mr'), 300);
});
</script>
{% endblock %}"""

content = open('app/templates/disease_result.html', 'r', encoding='utf-8').read()
marker = '</script>\n{% endblock %}'
if 'applyResultLanguage' not in content:
    content = content.replace(marker, '</script>' + translation_js, 1)
    open('app/templates/disease_result.html', 'w', encoding='utf-8').write(content)
    print('Done: translation JS injected')
else:
    print('Already present')
