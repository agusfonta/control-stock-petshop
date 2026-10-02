"""Usuarios router: alta solo por duena (sin registro publico)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import deps
from app.core.security import hash_password
from app.models import Usuario
from app.schemas import CrearUsuarioRequest, UsuarioResponse

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.post("", response_model=UsuarioResponse, status_code=201)
def crear_usuario(
    data: CrearUsuarioRequest,
    db: Session = Depends(deps.get_db),
    current: Usuario = Depends(deps.require_duena),
) -> UsuarioResponse:
    """Crea un usuario con password bcrypt; el password nunca se devuelve."""
    _ = current
    existente = db.query(Usuario).filter_by(email=data.email).one_or_none()
    if existente is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email ya registrado",
        )
    user = Usuario(
        email=data.email,
        password_hash=hash_password(data.password),
        rol=data.rol,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email ya registrado",
        ) from None
    db.refresh(user)
    return UsuarioResponse(
        id=user.id, email=user.email, rol=str(user.rol), activo=user.activo
    )
