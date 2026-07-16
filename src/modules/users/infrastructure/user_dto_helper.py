from src.modules.users.infrastructure.mapper import UserMapper
from src.modules.users.application.create import UserDTO

_mapper = UserMapper()


def user_to_dto(user_model) -> UserDTO:
    entity = _mapper.to_entity(user_model)
    dto = UserDTO.model_validate(entity)
    dto.parts_available = entity.parts_credit_limit - entity.total_parts_debt
    dto.service_available = entity.service_credit_limit - entity.total_service_debt
    return dto
