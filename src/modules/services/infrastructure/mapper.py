from src.core.infrastructure.mapper import GenericMapper
from src.modules.services.domain.entity import Service
from src.config.models import WorkshopService as ServiceModel


class ServiceMapper(GenericMapper[Service, ServiceModel]):
    def to_entity(self, model: ServiceModel) -> Service:
        return Service(
            id=model.id,
            workshop_id=model.workshop_id,
            service_name=model.service_name,
            service_type=model.service_type,
            standard_price_min=model.standard_price_min,
            standard_price_max=model.standard_price_max,
            revision_cost_min=model.revision_cost_min,
            revision_cost_max=model.revision_cost_max,
            vehicle_type=model.vehicle_type,
            created_at=model.created_at,
        )

    def to_model(self, entity: Service) -> ServiceModel:
        return ServiceModel(
            id=entity.id,
            workshop_id=entity.workshop_id,
            service_name=entity.service_name,
            service_type=entity.service_type,
            standard_price_min=entity.standard_price_min,
            standard_price_max=entity.standard_price_max,
            revision_cost_min=entity.revision_cost_min,
            revision_cost_max=entity.revision_cost_max,
            vehicle_type=entity.vehicle_type,
            created_at=entity.created_at,
        )
