from src.core.infrastructure.mapper import GenericMapper
from src.modules.workshops.domain.entity import (
    Workshop,
    WorkshopBankAccount,
    WorkshopMobilePayment,
    WorkshopPaymentMethod,
)
from src.config.models import Workshop as WorkshopModel
from src.config.models import (
    WorkshopBankAccount as WorkshopBankAccountModel,
)
from src.config.models import (
    WorkshopMobilePayment as WorkshopMobilePaymentModel,
)
from src.config.models import (
    WorkshopPaymentMethod as WorkshopPaymentMethodModel,
)


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
            was_certified=model.was_certified,
            is_suspended=model.is_suspended,
            average_rating=model.average_rating,
            verification_document_url=model.verification_document_url,
            photo_url=model.photo_url,
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
            was_certified=entity.was_certified,
            is_suspended=entity.is_suspended,
            average_rating=entity.average_rating,
            verification_document_url=entity.verification_document_url,
            photo_url=entity.photo_url,
            created_at=entity.created_at,
        )


class WorkshopBankAccountMapper(
    GenericMapper[WorkshopBankAccount, WorkshopBankAccountModel]
):
    def to_entity(self, model: WorkshopBankAccountModel) -> WorkshopBankAccount:
        return WorkshopBankAccount(
            id=model.id,
            workshop_id=model.workshop_id,
            account_number=model.account_number,
            holder_ci=model.holder_ci,
            bank_name=model.bank_name,
            is_active=model.is_active,
        )

    def to_model(self, entity: WorkshopBankAccount) -> WorkshopBankAccountModel:
        return WorkshopBankAccountModel(
            id=entity.id,
            workshop_id=entity.workshop_id,
            account_number=entity.account_number,
            holder_ci=entity.holder_ci,
            bank_name=entity.bank_name,
            is_active=entity.is_active,
        )


class WorkshopMobilePaymentMapper(
    GenericMapper[WorkshopMobilePayment, WorkshopMobilePaymentModel]
):
    def to_entity(self, model: WorkshopMobilePaymentModel) -> WorkshopMobilePayment:
        return WorkshopMobilePayment(
            id=model.id,
            workshop_id=model.workshop_id,
            phone_number=model.phone_number,
            bank_name=model.bank_name,
            holder_ci=model.holder_ci,
            is_active=model.is_active,
        )

    def to_model(self, entity: WorkshopMobilePayment) -> WorkshopMobilePaymentModel:
        return WorkshopMobilePaymentModel(
            id=entity.id,
            workshop_id=entity.workshop_id,
            phone_number=entity.phone_number,
            bank_name=entity.bank_name,
            holder_ci=entity.holder_ci,
            is_active=entity.is_active,
        )


class WorkshopPaymentMethodMapper(
    GenericMapper[WorkshopPaymentMethod, WorkshopPaymentMethodModel]
):
    def to_entity(self, model: WorkshopPaymentMethodModel) -> WorkshopPaymentMethod:
        return WorkshopPaymentMethod(
            id=model.id,
            workshop_id=model.workshop_id,
            type=model.type,
            bank_name=model.bank_name,
            account_number=model.account_number,
            account_holder=model.account_holder,
            phone_number=model.phone_number,
            holder_ci=model.holder_ci,
            is_active=model.is_active,
        )

    def to_model(self, entity: WorkshopPaymentMethod) -> WorkshopPaymentMethodModel:
        return WorkshopPaymentMethodModel(
            id=entity.id,
            workshop_id=entity.workshop_id,
            type=entity.type,
            bank_name=entity.bank_name,
            account_number=entity.account_number,
            account_holder=entity.account_holder,
            phone_number=entity.phone_number,
            holder_ci=entity.holder_ci,
            is_active=entity.is_active,
        )
