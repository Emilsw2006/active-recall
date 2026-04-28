"""
Endpoints de documentos:
- POST /documento/upload              → sube PDF, dispara background task
- GET  /documento/{id}/estado         → polling del estado
- GET  /documento/{id}/temas          → estructura completa con conteos
- GET  /documentos/asignatura/{id}    → documentos de una asignatura (con n_atomos)
- GET  /documentos/asignatura/{id}/temas → lista plana de temas para el lobby
- DELETE /documento/{id}              → elimina documento y sus datos
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks

from utils.logger import get_logger
from utils.supabase_client import get_service_client
from core.ingestion import procesar_pdf

logger = get_logger(__name__)
router = APIRouter(tags=["documentos"])


@router.post("/documento/upload")
async def upload_documento(
    background_tasks: BackgroundTasks,
    pdf_file: UploadFile = File(...),
    usuario_id: str = Form(...),
    asignatura_id: str = Form(...),
):
    db = get_service_client()
    logger.info(f"Upload: '{pdf_file.filename}' usuario={usuario_id} asignatura={asignatura_id}")

    if not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    res = (
        db.table("documentos")
        .insert({
            "asignatura_id": asignatura_id,
            "usuario_id": usuario_id,
            "nombre_archivo": pdf_file.filename,
            "estado": "procesando",
        })
        .execute()
    )
    documento_id = res.data[0]["id"]
    logger.info(f"Documento creado: {documento_id} — procesamiento en background")

    pdf_bytes = await pdf_file.read()

    background_tasks.add_task(
        procesar_pdf,
        pdf_bytes=pdf_bytes,
        documento_id=documento_id,
        asignatura_id=asignatura_id,
        usuario_id=usuario_id,
    )

    return {"documento_id": documento_id, "estado": "procesando"}


@router.get("/documentos/asignatura/{asignatura_id}/temas")
async def temas_por_asignatura(asignatura_id: str):
    """Devuelve lista plana de temas para el lobby de sesión."""
    db = get_service_client()

    docs_res = (
        db.table("documentos")
        .select("id, nombre_archivo, estado")
        .eq("asignatura_id", asignatura_id)
        .eq("estado", "listo")
        .execute()
    )
    docs = docs_res.data or []

    temas_out = []
    for doc in docs:
        temas_res = (
            db.table("temas")
            .select("id, titulo, orden")
            .eq("documento_id", doc["id"])
            .order("orden")
            .execute()
        )
        for tema in (temas_res.data or []):
            st_res = db.table("subtemas").select("id").eq("tema_id", tema["id"]).execute()
            st_ids = [s["id"] for s in (st_res.data or [])]
            n_atomos = 0
            n_practicos = 0
            n_teoricos = 0
            for sid in st_ids:
                a_res = db.table("atomos").select("id, tipo").eq("subtema_id", sid).execute()
                atoms = a_res.data or []
                n_atomos += len(atoms)
                n_practicos += sum(1 for a in atoms if (a.get("tipo") or "teorico") == "practico")
                n_teoricos += sum(1 for a in atoms if (a.get("tipo") or "teorico") != "practico")
            tipo_agg = "teorico" if n_practicos == 0 else ("practico" if n_teoricos == 0 else "mixto")
            temas_out.append({
                "id": tema["id"],
                "titulo": tema["titulo"],
                "n_atomos": n_atomos,
                "n_practicos": n_practicos,
                "n_teoricos": n_teoricos,
                "tipo_agg": tipo_agg,
                "documento_id": doc["id"],
                "documento_nombre": doc["nombre_archivo"],
            })

    return temas_out


@router.get("/documentos/asignatura/{asignatura_id}")
async def documentos_por_asignatura(asignatura_id: str):
    db = get_service_client()
    res = (
        db.table("documentos")
        .select("id, nombre_archivo, estado, error_mensaje, fecha_subida")
        .eq("asignatura_id", asignatura_id)
        .order("fecha_subida", desc=True)
        .execute()
    )
    docs = res.data or []

    # Enrich with atom count
    for doc in docs:
        try:
            temas_res = db.table("temas").select("id").eq("documento_id", doc["id"]).execute()
            tema_ids = [t["id"] for t in (temas_res.data or [])]
            n_atomos = 0
            for tid in tema_ids:
                st_res = db.table("subtemas").select("id").eq("tema_id", tid).execute()
                st_ids = [s["id"] for s in (st_res.data or [])]
                for sid in st_ids:
                    a_res = db.table("atomos").select("id", count="exact").eq("subtema_id", sid).execute()
                    n_atomos += a_res.count or 0
            doc["n_atomos"] = n_atomos
        except Exception:
            doc["n_atomos"] = 0

    return docs


@router.delete("/documento/{documento_id}")
async def eliminar_documento(documento_id: str):
    """Elimina un documento y todos sus datos asociados."""
    db = get_service_client()
    temas_res = db.table("temas").select("id").eq("documento_id", documento_id).execute()
    tema_ids = [t["id"] for t in (temas_res.data or [])]
    for tid in tema_ids:
        st_res = db.table("subtemas").select("id").eq("tema_id", tid).execute()
        st_ids = [s["id"] for s in (st_res.data or [])]
        for sid in st_ids:
            db.table("atomos").delete().eq("subtema_id", sid).execute()
        db.table("subtemas").delete().eq("tema_id", tid).execute()
    db.table("temas").delete().eq("documento_id", documento_id).execute()
    db.table("documentos").delete().eq("id", documento_id).execute()
    logger.info(f"Documento {documento_id} eliminado")
    return {"ok": True}


@router.get("/documento/{documento_id}/estado")
async def estado_documento(documento_id: str):
    db = get_service_client()
    res = (
        db.table("documentos")
        .select("id, estado, nombre_archivo, error_mensaje, fecha_subida")
        .eq("id", documento_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return res.data[0]


@router.get("/documento/{documento_id}/temas")
async def temas_documento(documento_id: str):
    db = get_service_client()

    doc_res = db.table("documentos").select("estado, nombre_archivo").eq("id", documento_id).execute()
    if not doc_res.data:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    doc = doc_res.data[0]
    if doc["estado"] != "listo":
        raise HTTPException(
            status_code=400,
            detail=f"Documento en estado '{doc['estado']}', espera a que esté 'listo'"
        )

    temas_res = (
        db.table("temas")
        .select("id, titulo, orden")
        .eq("documento_id", documento_id)
        .order("orden")
        .execute()
    )

    resultado = []
    for tema in temas_res.data:
        subtemas_res = (
            db.table("subtemas")
            .select("id, titulo, orden")
            .eq("tema_id", tema["id"])
            .order("orden")
            .execute()
        )

        subtemas_con_conteo = []
        total_atomos_tema = 0

        for subtema in subtemas_res.data:
            # Obtener átomos con su tipo para poder derivar tipo_agg
            atomos_res = (
                db.table("atomos")
                .select("id, tipo")
                .eq("subtema_id", subtema["id"])
                .execute()
            )
            atomos_data = atomos_res.data or []
            n_atomos = len(atomos_data)
            n_practicos = sum(1 for a in atomos_data if (a.get("tipo") or "teorico") == "practico")
            n_teoricos = n_atomos - n_practicos
            if n_practicos == 0:
                tipo_agg = "teorico"
            elif n_teoricos == 0:
                tipo_agg = "practico"
            else:
                tipo_agg = "mixto"
            total_atomos_tema += n_atomos
            subtemas_con_conteo.append({
                **subtema,
                "n_atomos": n_atomos,
                "n_practicos": n_practicos,
                "n_teoricos": n_teoricos,
                "tipo_agg": tipo_agg,
            })

        resultado.append({
            **tema,
            "n_atomos": total_atomos_tema,
            "subtemas": subtemas_con_conteo,
        })

    return {
        "documento_id": documento_id,
        "nombre_archivo": doc["nombre_archivo"],
        "temas": resultado,
    }
