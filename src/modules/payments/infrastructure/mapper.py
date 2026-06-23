from src.core.infrastructure.mapper import GenericMapper
from src.modules.payments.domain.entity import UserPaymentAccount
from src.config.models import UserPaymentAccount as UserPaymentAccountModel


class UserPaymentAccountMapper(
    GenericMapper[UserPaymentAccount, UserPaymentAccountModel]
):
    def to_entity(self, model: UserPaymentAccountModel) -> UserPaymentAccount:
        return UserPaymentAccount(
            id=model.id,
            user_id=model.user_id,
            account_type=model.account_type,
            bank_name=model.bank_name,
            holder_document=model.holder_document,
            account_number=model.account_number,
            account_holder=model.account_holder,
            phone_number=model.phone_number,
            is_active=model.is_active,
            created_at=model.created_at,
        )

    def to_model(self, entity: UserPaymentAccount) -> UserPaymentAccountModel:
        return UserPaymentAccountModel(
            id=entity.id,
            user_id=entity.user_id,
            account_type=entity.account_type,
            bank_name=entity.bank_name,
            holder_document=entity.holder_document,
            account_number=entity.account_number,
            account_holder=entity.account_holder,
            phone_number=entity.phone_number,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )
