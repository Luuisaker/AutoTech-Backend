from src.core.infrastructure.mapper import GenericMapper
from src.modules.users.domain.entity import User
from src.config.models import User as UserModel
from src.config.models import UserRole
from src.modules.users.infrastructure.auth import ROLE_NAME_TO_UUID, ROLE_UUID_TO_NAME


class UserMapper(GenericMapper[User, UserModel]):
    def to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            roles=[ROLE_UUID_TO_NAME.get(str(ur.role_id), "CLIENT") for ur in model.roles],
            photo_url=model.photo_url,
            first_name=model.first_name,
            last_name=model.last_name,
            ci=model.ci,
            phone=model.phone,
            is_suspended=model.is_suspended,
            client_average_rating=model.client_average_rating,
            client_rating_count=model.client_rating_count,
            credit_level=model.credit_level,
            parts_credit_limit=model.parts_credit_limit,
            service_credit_limit=model.service_credit_limit,
            credit_points=model.credit_points,
            total_parts_debt=model.total_parts_debt,
            total_service_debt=model.total_service_debt,
            is_2fa_enabled=model.is_2fa_enabled,
            language_preference=model.language_preference,
            created_at=model.created_at,
        )

    def to_model(self, entity: User) -> UserModel:
        model = UserModel(
            id=entity.id,
            email=entity.email,
            password_hash=entity.password_hash,
            photo_url=entity.photo_url,
            first_name=entity.first_name,
            last_name=entity.last_name,
            ci=entity.ci,
            phone=entity.phone,
            client_average_rating=entity.client_average_rating,
            client_rating_count=entity.client_rating_count,
            credit_level=entity.credit_level,
            parts_credit_limit=entity.parts_credit_limit,
            service_credit_limit=entity.service_credit_limit,
            credit_points=entity.credit_points,
            total_parts_debt=entity.total_parts_debt,
            total_service_debt=entity.total_service_debt,
            language_preference=entity.language_preference,
            created_at=entity.created_at,
        )
        model.roles = [UserRole(role_id=ROLE_NAME_TO_UUID.get(r, r), user_id=entity.id) for r in entity.roles]
        return model
