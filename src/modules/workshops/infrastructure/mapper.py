from src.core.infrastructure.mapper import GenericMapper
from src.modules.workshops.domain.entity import Workshop
from src.config.models import Workshop as WorkshopModel


class WorkshopMapper(GenericMapper[Workshop, WorkshopModel]):
    def to_entity(self, model: WorkshopModel) -> Workshop:
        return Workshop(
            id=model.id,
            owner_id=model.owner_id,
            name=model.name,
            rif=model.rif,
            address=model.address,
            latitude=model.latitude,
            longitude=model.longitude,
            is_certified=model.is_certified,
            average_rating=model.average_rating,
            verification_document_url=model.verification_document_url,
            created_at=model.created_at,
        )

    def to_model(self, entity: Workshop) -> WorkshopModel:
        return WorkshopModel(
            id=entity.id,
            owner_id=entity.owner_id,
            name=entity.name,
            rif=entity.rif,
            address=entity.address,
            latitude=entity.latitude,
            longitude=entity.longitude,
            is_certified=entity.is_certified,
            average_rating=entity.average_rating,
            verification_document_url=entity.verification_document_url,
            created_at=entity.created_at,
        )
