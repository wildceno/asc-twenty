"""Twenty biçimli metin (RICH_TEXT) değeri. API'ye yalnız markdown yazılınca kayıt ekranının gösterdiği blok biçimi
boş kalıyor (14 Kas 2026'da denendi); ikisi birlikte yazılır."""
import json
import uuid


def zengin_metin(markdown):
    """Düz metin / basit markdown → {'markdown', 'blocknote'} (her satır bir paragraf)."""
    bloklar = []
    for satir in (markdown or "").split("\n"):
        bloklar.append({"id": str(uuid.uuid4()), "type": "paragraph",
                        "props": {"textColor": "default", "backgroundColor": "default", "textAlignment": "left"},
                        "content": [{"type": "text", "text": satir, "styles": {}}] if satir else [], "children": []})
    return {"markdown": markdown or "", "blocknote": json.dumps(bloklar, ensure_ascii=False)}
