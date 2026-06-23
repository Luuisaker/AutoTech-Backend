from src.core.infrastructure.mapper import GenericMapper
from src.modules.users.domain.entity import User
from src.config.models import User as UserModel
from src.config.models import UserRole


class UserMapper(GenericMapper[User, UserModel]):
    def to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            roles=[ur.role for ur in model.roles],
            first_name=model.first_name,
            last_name=model.last_name,
            ci=model.ci,
            phone=model.phone,
            created_at=model.created_at,
        )

    def to_model(self, entity: User) -> UserModel:
        model = UserModel(
            id=entity.id,
            email=entity.email,
            password_hash=entity.password_hash,
            first_name=entity.first_name,
            last_name=entity.last_name,
            ci=entity.ci,
            phone=entity.phone,
            created_at=entity.created_at,
        )
        model.roles = [UserRole(role=r, user_id=entity.id) for r in entity.roles]
        return model
