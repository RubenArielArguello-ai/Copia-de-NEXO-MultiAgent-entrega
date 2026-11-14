#!/usr/bin/env python3
"""Generate NEXO's editable PowerPoint using only Python stdlib."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parents[1] / "NEXO_FINAL.pptx"
EMU = 914400
W, H = 13.333 * EMU, 7.5 * EMU
NAVY, PANEL, CYAN, WHITE, MUTED = "08111F", "111E30", "42D6C8", "F2F6FC", "AAB8CB"

slides = [
 ("NEXO MultiAgent", ["Sistema multiagente local para resolver misiones técnicas", "Defensa académica · Arquitectura, agentes y evidencia"]),
 ("El problema", ["Una solicitud técnica suele exigir análisis, planificación, ejecución y revisión.", "Un único paso de generación mezcla esas responsabilidades y dificulta auditar errores.", "NEXO separa roles y conserva evidencia del proceso."]),
 ("Objetivos", ["Coordinar cuatro agentes especializados con contratos claros.", "Ejecutar herramientas y fundamentar conclusiones en observaciones.", "Limitar reintentos, registrar mensajes y persistir solo resultados aprobados.", "Permitir operación local con Ollama."]),
 ("Arquitectura general", ["Dashboard web o Streamlit → FastAPI → Orquestador → Analista → Estratega → Ejecutor → Evaluador", "SQLite registra sesiones, mensajes, herramientas y eventos.", "Chroma recupera experiencias aprobadas; Ollama sirve modelos y embeddings."]),
 ("Tecnologías", ["Python: agentes, coordinación y herramientas · FastAPI/Uvicorn: API REST", "HTML/CSS/JavaScript: Dashboard web · Streamlit: cliente complementario", "Ollama: inferencia local · SQLite: trazabilidad · Chroma: memoria vectorial · Docker Compose: servicios"]),
 ("Modelos locales", ["Cuatro agentes: qwen2.5-coder:7b (predeterminado y JSON estructurado validado)", "Memoria vectorial: nomic-embed-text", "Gemma4 está instalado pero no respetó el contrato JSON en la misión observada.", "Los modelos deben estar disponibles en Ollama antes de iniciar."]),
 ("Los cuatro agentes", ["Analista: interpreta la solicitud, restricciones y criterios verificables.", "Estratega: convierte el análisis en tareas con dependencias.", "Ejecutor: obtiene evidencia mediante herramientas autorizadas.", "Evaluador: contrasta resultados y criterios; devuelve aprobación o correcciones."]),
 ("Orquestación y comunicación", ["El orquestador es lógica Python: gestiona fases, bus de mensajes y estado.", "Cada mensaje guarda remitente, destinatario, fase, estado y carga útil.", "Máximos configurables: iteraciones y ciclos de replanificación; sin bucles infinitos."]),
 ("Memoria persistente", ["SQLite conserva el historial operacional.", "Chroma indexa semánticamente resultados aprobados con nomic-embed-text.", "Antes de analizar, se recupera contexto similar; no sustituye evidencia nueva.", "Resultados rechazados no se registran como aprobados."]),
 ("Herramientas", ["ToolRegistry: diagnóstico de red, sistema, puertos TCP y archivos de texto.", "file_read y file_write limitan las rutas al directorio de trabajo del proyecto.", "Cada ejecución guarda parámetros, salida, duración y éxito en SQLite.", "La salida observada por la herramienta se mantiene separada de la interpretación del LLM."]),
 ("Mapa de módulos", ["api/main.py — Endpoints REST, estado de modelos y servicio del frontend.", "nexo/core/ — Orquestación, estado, bus de mensajes, coherencia y memoria.", "nexo/agents/ — Contratos de Analista, Estratega, Ejecutor y Evaluador.", "nexo/providers/ — Ollama real y MockProvider explícito para pruebas.", "nexo/tools/ — Herramientas registradas y validación de operaciones.", "frontend/ + app.py — Dashboard web y cliente Streamlit de FastAPI."]),
 ("Dashboard", ["Estado/modelo de agentes y conexión Ollama.", "Plan, flujo de mensajes, herramientas, memoria y coherencia.", "Historial, errores, duración y métricas derivadas de SQLite.", "El botón Ejecutar inicia POST /sessions y el navegador consulta el progreso."]),
 ("Misión demostrable", ["Solicitud ejecutada: crear prueba_nexo_toolregistry.txt con texto exacto y luego leerlo.", "Analista interpretó el objetivo; Estratega generó escritura y lectura ordenadas.", "Ejecutor llamó file_write y file_read; ambas salidas observaron el mismo contenido.", "Evaluador contrastó el contenido leído con el pedido original."]),
 ("Evidencia y resultados", ["Misión Ollama real: COMPLETED · APPROVED · 1 iteración · 10 mensajes · 138,01 s.", "Dos tareas completadas: file_write y file_read; ambas observaron el texto solicitado.", "Archivo: prueba_nexo_toolregistry.txt · SQLite guardó la sesión aprobada.", "Chroma conservó recuerdos; approved se deriva del veredicto del Evaluador."]),
 ("Recuperación y límites", ["JSON inválido del Estratega: plan mínimo derivado del objetivo y herramientas disponibles.", "Errores de modelos: contratos de fallback; el Evaluador falla cerrado.", "Rechazo: replanificación con límites de iteraciones configurables.", "La evaluación LLM y la selección de herramientas por texto siguen siendo probabilísticas."]),
 ("Conclusiones", ["La especialización separa interpretación, planificación, acción y control.", "La trazabilidad permite revisar evidencia, decisiones, correcciones y fallos.", "COMPLETED significa sesión finalizada; APPROVED es un veredicto independiente.", "La demostración es una ejecución real reproducible, no una evaluación estadística del sistema."]),
 ("Inicio para la defensa", ["Terminal 1: ollama serve (si Ollama no está ejecutándose como servicio).", "Terminal 2: uvicorn api.main:app --reload --host 127.0.0.1 --port 8000", "Abrir http://127.0.0.1:8000 y revisar conexión, modelos y herramientas.", "Misión recomendada: repetir la solicitud de archivo mostrada en la diapositiva anterior.", "Vista alternativa: NEXO_API_URL=http://127.0.0.1:8000 streamlit run app.py"]),
 ("Mejoras futuras", ["Añadir autenticación y restringir CORS para despliegues públicos.", "Aislar rutas auxiliares de ejecución Python con permisos mínimos.", "Medir latencia por agente y evaluar un conjunto diverso de misiones.", "Agregar streaming de eventos y exportación de reportes de sesión."]),
]

def xml_escape(s): return escape(str(s))
def shape_text(sid, name, text, x, y, w, h, size=1900, color=WHITE, bold=False):
    runs = []
    for i, line in enumerate(text.split("\n")):
        runs.append(f'<a:p><a:pPr marL="0" indent="0"/><a:r><a:rPr lang="es-AR" sz="{size}" b="{1 if bold else 0}" dirty="0"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="Aptos"/></a:rPr><a:t>{xml_escape(line)}</a:t></a:r><a:endParaRPr lang="es-AR" sz="{size}"/></a:p>')
    return f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{xml_escape(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(w)}" cy="{int(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" anchor="t"><a:spAutoFit/></a:bodyPr><a:lstStyle/>{''.join(runs)}</p:txBody></p:sp>'

def shape_rect(sid, x, y, w, h, fill, line=None, radius="roundRect"):
    ln = f'<a:ln w="19050"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>' if line else '<a:ln><a:noFill/></a:ln>'
    return f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="Panel {sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{int(x)}" y="{int(y)}"/><a:ext cx="{int(w)}" cy="{int(h)}"/></a:xfrm><a:prstGeom prst="{radius}"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>{ln}</p:spPr></p:sp>'

def slide_xml(title, bullets, number):
    shapes = [shape_rect(2, 0, 0, W, H, NAVY, radius="rect"), shape_rect(3, 0, 0, 0.12*EMU, H, CYAN, radius="rect")]
    shapes.append(shape_text(4, "Title", title, 0.72*EMU, 0.48*EMU, 11.9*EMU, 0.75*EMU, 2900, WHITE, True))
    shapes.append(shape_rect(5, 0.72*EMU, 1.38*EMU, 11.88*EMU, 0.03*EMU, CYAN, radius="rect"))
    if title == "Mapa de módulos":
        cards = []
        for i, bullet in enumerate(bullets):
            heading, _, detail = bullet.partition(" — ")
            row, col = divmod(i, 3)
            x, y = (0.82 + col*4.08)*EMU, (1.75 + row*2.18)*EMU
            cards.append(shape_rect(40+i, x, y, 3.68*EMU, 1.78*EMU, PANEL, CYAN if i in (0, 1) else None))
            cards.append(shape_text(50+i, f"Module {heading}", heading, x+0.18*EMU, y+0.2*EMU, 3.3*EMU, 0.38*EMU, 1450, CYAN, True))
            cards.append(shape_text(60+i, f"Detail {heading}", detail, x+0.18*EMU, y+0.68*EMU, 3.3*EMU, 0.92*EMU, 1200, WHITE))
        shapes.extend(cards)
    # A visual four-stage strip appears on architecture/agent/flow slides.
    elif number in (4, 7, 8):
        labels = ["ANALISTA", "ESTRATEGA", "EJECUTOR", "EVALUADOR"]
        for i, label in enumerate(labels):
            x = (0.85 + i*3.05)*EMU
            shapes.append(shape_rect(10+i, x, 1.72*EMU, 2.4*EMU, 0.60*EMU, PANEL, CYAN))
            shapes.append(shape_text(20+i, label, label, x+0.1*EMU, 1.91*EMU, 2.2*EMU, 0.3*EMU, 1300, CYAN, True))
            if i < 3:
                shapes.append(shape_text(30+i, "Arrow", "→", x+2.48*EMU, 1.83*EMU, 0.45*EMU, 0.4*EMU, 2000, WHITE, True))
        top = 2.65
    else: top = 1.72
    if title != "Mapa de módulos":
        body = "\n".join("•  " + b for b in bullets)
        shapes.append(shape_rect(6, 0.72*EMU, top*EMU, 11.88*EMU, (6.25-top)*EMU, PANEL, radius="roundRect"))
        shapes.append(shape_text(7, "Content", body, 1.05*EMU, (top+0.25)*EMU, 11.2*EMU, (6.0-top)*EMU, 1750, WHITE))
    shapes.append(shape_text(8, "Footer", f"NEXO MultiAgent  ·  {number:02d} / {len(slides)}", 9.0*EMU, 7.08*EMU, 3.55*EMU, 0.22*EMU, 900, MUTED))
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>{"".join(shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'

def main():
    content_types = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/><Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>' + ''.join(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' for i in range(1,len(slides)+1)) + '</Types>'
    relroot = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>'
    ids = ''.join(f'<p:sldId id="{255+i}" r:id="rId{i+1}"/>' for i in range(1,len(slides)+1))
    pres = f'<?xml version="1.0" encoding="UTF-8"?><p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>{ids}</p:sldIdLst><p:sldSz cx="{int(W)}" cy="{int(H)}" type="wide"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>' + ''.join(f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>' for i in range(1,len(slides)+1)) + '</Relationships>'
    with ZipFile(OUT, 'w', ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', relroot)
        z.writestr('ppt/presentation.xml', pres)
        z.writestr('ppt/_rels/presentation.xml.rels', rels)
        z.writestr('ppt/slideMasters/slideMaster1.xml', '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap accent1="42D6C8" accent2="111E30" accent3="F2F6FC" accent4="AAB8CB" accent5="08111F" accent6="08111F" bg1="FFFFFF" bg2="08111F" folHlink="FF00FF" hlink="0000FF" tx1="000000" tx2="FFFFFF"/><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>')
        z.writestr('ppt/slideMasters/_rels/slideMaster1.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>')
        z.writestr('ppt/slideLayouts/slideLayout1.xml', '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')
        z.writestr('ppt/slideLayouts/_rels/slideLayout1.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>')
        for i, (title, bullets) in enumerate(slides, 1):
            z.writestr(f'ppt/slides/slide{i}.xml', slide_xml(title, bullets, i))
            z.writestr(f'ppt/slides/_rels/slide{i}.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/></Relationships>')
    print(OUT)

if __name__ == '__main__': main()
