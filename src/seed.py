import asyncio
import uuid

import bcrypt

from src.config.database import session_factory
from src.config.models import (
    User as UserModel,
    UserRole,
    Role as RoleModel,
    Vehicle as VehicleModel,
    Workshop as WorkshopModel,
    WorkshopBankAccount as WorkshopBankAccountModel,
    WorkshopMobilePayment as WorkshopMobilePaymentModel,
    WorkshopService as WorkshopServiceModel,
    Part as PartModel,
    UserPaymentAccount as UserPaymentAccountModel,
)


PASSWORD = "string"
HASHED = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()

from src.modules.users.infrastructure.auth import ROLE_NAME_TO_UUID
from src.modules.users.domain.role import RoleName


async def seed() -> None:
    session = session_factory()
    async with session:
        # ── ROLES ───────────────────────────────────────────────
        for name, role_id in ROLE_NAME_TO_UUID.items():
            existing = await session.get(RoleModel, uuid.UUID(role_id))
            if not existing:
                session.add(RoleModel(id=uuid.UUID(role_id), name=name))
        await session.flush()
        print("[OK] Roles verificados/creados")

        # ── USERS ──────────────────────────────────────────────

        user1 = UserModel(
            email="user@example.com",
            password_hash=HASHED,
            first_name="Carlos",
            last_name="Martínez",
            ci="V-12345678",
            phone="04121234567",
            roles=[UserRole(role_id=ROLE_NAME_TO_UUID[RoleName.CLIENT]), UserRole(role_id=ROLE_NAME_TO_UUID[RoleName.WORKSHOP_OWNER])],
        )
        session.add(user1)

        user2 = UserModel(
            email="maria@example.com",
            password_hash=HASHED,
            first_name="María",
            last_name="Rodríguez",
            ci="V-23456789",
            phone="04141234567",
            roles=[UserRole(role_id=ROLE_NAME_TO_UUID[RoleName.CLIENT])],
        )
        session.add(user2)

        user3 = UserModel(
            email="admin@example.com",
            password_hash=HASHED,
            first_name="Admin",
            last_name="Sistema",
            ci="V-11111111",
            phone="04241234567",
            roles=[UserRole(role_id=ROLE_NAME_TO_UUID[RoleName.ADMIN])],
        )
        session.add(user3)

        superadmin_hash = bcrypt.hashpw("SUPER123*".encode(), bcrypt.gensalt()).decode()
        user4 = UserModel(
            email="superadmin@gmail.com",
            password_hash=superadmin_hash,
            first_name="superman",
            last_name="SuperAdmin",
            ci="V-99999999",
            phone="04249999999",
            roles=[UserRole(role_id=ROLE_NAME_TO_UUID[RoleName.SUPERADMIN])],
        )
        session.add(user4)

        await session.flush()

        print("[OK] Usuarios creados:")
        print(f"  user@example.com  (Carlos, WORKSHOP_OWNER + CLIENT) -- id={user1.id}")
        print(f"  maria@example.com  (Maria, CLIENT)                 -- id={user2.id}")
        print(f"  admin@example.com (Admin, ADMIN)                   -- id={user3.id}")
        print(f"  gabrielsylar554@gmail.com (Gabriel, SUPERADMIN)     -- id={user4.id}")

        # ── VEHICLES ────────────────────────────────────────────

        vehicles_data = [
            VehicleModel(
                owner_id=user1.id,
                vehicle_type="CAR",
                brand="Chevrolet",
                model="Onix",
                year=2020,
                license_plate="ABC123",
                vin="1G1ZK5SU7KF123456",
            ),
            VehicleModel(
                owner_id=user1.id,
                vehicle_type="CAR",
                brand="Toyota",
                model="Corolla",
                year=2022,
                license_plate="DEF456",
                vin="2T1BURHE6KC123457",
            ),
            VehicleModel(
                owner_id=user2.id,
                vehicle_type="CAR",
                brand="Ford",
                model="Explorer",
                year=2019,
                license_plate="GHI789",
                vin="1FM5K8D89KGA12345",
            ),
            VehicleModel(
                owner_id=user2.id,
                vehicle_type="CAR",
                brand="Hyundai",
                model="Elantra",
                year=2021,
                license_plate="JKL012",
                vin="5NPEG4JA4MH123458",
            ),
        ]
        for v in vehicles_data:
            session.add(v)
        await session.flush()
        print(f"[OK] {len(vehicles_data)} vehículos creados")

        # ── WORKSHOPS ───────────────────────────────────────────

        workshop_verified = WorkshopModel(
            owner_id=user1.id,
            name="AutoMecánica Central",
            rif="J-123456789",
            address="Av. Principal de Las Mercedes, Edif. AutoCenter, PB, Caracas",
            latitude=10.4806,
            longitude=-66.9036,
            is_certified=1,
            verification_document_url="/uploads/verification_documents/w1_doc.pdf",
        )
        session.add(workshop_verified)

        workshop_unverified = WorkshopModel(
            owner_id=user1.id,
            name="Taller El Chicó",
            rif="J-987654321",
            address="Calle Los Mangos, Qta. El Taller, Caracas",
            latitude=10.4960,
            longitude=-66.8480,
            is_certified=0,
            verification_document_url="/uploads/verification_documents/w2_doc.pdf",
        )
        session.add(workshop_unverified)

        await session.flush()
        print("[OK] Talleres creados:")
        print(
            f"  {workshop_verified.name}   (certificado)   -- id={workshop_verified.id}"
        )
        print(
            f"  {workshop_unverified.name} (no certificado) -- id={workshop_unverified.id}"
        )

        # ── BANK ACCOUNTS (verified workshop) ───────────────────

        bank_accounts = [
            WorkshopBankAccountModel(
                workshop_id=workshop_verified.id,
                account_number="01340123456789012345",
                holder_ci="V-12345678",
                bank_name="Banesco",
            ),
            WorkshopBankAccountModel(
                workshop_id=workshop_verified.id,
                account_number="01050123456789012345",
                holder_ci="V-12345678",
                bank_name="Mercantil Banco",
            ),
        ]
        for b in bank_accounts:
            session.add(b)

        # ── MOBILE PAYMENTS (verified workshop) ─────────────────

        mobile_payments = [
            WorkshopMobilePaymentModel(
                workshop_id=workshop_verified.id,
                phone_number="04121234567",
                bank_name="Banesco",
                holder_ci="V-12345678",
            ),
            WorkshopMobilePaymentModel(
                workshop_id=workshop_verified.id,
                phone_number="04147654321",
                bank_name="Mercantil Banco",
                holder_ci="V-12345678",
            ),
        ]
        for m in mobile_payments:
            session.add(m)
        print(
            f"[OK] {len(bank_accounts)} cuentas bancarias + {len(mobile_payments)} pagos móviles creados"
        )

        # ── SERVICES (verified workshop) ────────────────────────

        services_data = [
            WorkshopServiceModel(
                workshop_id=workshop_verified.id,
                service_name="Cambio de aceite",
                standard_price_min=15.0,
                standard_price_max=25.0,
            ),
            WorkshopServiceModel(
                workshop_id=workshop_verified.id,
                service_name="Alineación y balanceo",
                standard_price_min=30.0,
                standard_price_max=50.0,
            ),
            WorkshopServiceModel(
                workshop_id=workshop_verified.id,
                service_name="Diagnóstico computarizado",
                standard_price_min=20.0,
                standard_price_max=40.0,
            ),
            WorkshopServiceModel(
                workshop_id=workshop_verified.id,
                service_name="Cambio de pastillas de freno",
                standard_price_min=60.0,
                standard_price_max=120.0,
            ),
            WorkshopServiceModel(
                workshop_id=workshop_verified.id,
                service_name="Reparación de aire acondicionado",
                standard_price_min=80.0,
                standard_price_max=200.0,
            ),
        ]
        for s in services_data:
            session.add(s)
        print(f"[OK] {len(services_data)} servicios creados")

        # ── PARTS (verified workshop) ───────────────────────────

        parts_verified = [
            PartModel(
                workshop_id=workshop_verified.id,
                name="Pastillas de freno cerámicas",
                description="Pastillas de freno delanteras cerámicas, compatibles con Chevrolet Onix 2020-2023",
                price=45.50,
                stock=20,
                condition="NEW",
                category="BRAKES",
                allows_installments=1,
                installment_min_percentage=30.0,
            ),
            PartModel(
                workshop_id=workshop_verified.id,
                name="Filtro de aceite premium",
                description="Filtro de aceite de alta eficiencia, compatible con la mayoría de motores gasolina 4 cilindros",
                price=12.00,
                stock=50,
                condition="NEW",
                category="CONSUMABLE",
                allows_installments=0,
                installment_min_percentage=0.0,
            ),
            PartModel(
                workshop_id=workshop_verified.id,
                name="Batería 12V 60Ah",
                description="Batería libre de mantenimiento, 12 voltios 60 amperios, arranque en frío 540A",
                price=85.00,
                stock=10,
                condition="NEW",
                category="ELECTRICAL",
                allows_installments=1,
                installment_min_percentage=20.0,
            ),
            PartModel(
                workshop_id=workshop_verified.id,
                name="Espejo retrovisor izquierdo",
                description="Espejo retrovisor lateral izquierdo, color negro, toyota corolla 2018-2022",
                price=25.00,
                stock=5,
                condition="USED",
                category="BODY",
                allows_installments=0,
                installment_min_percentage=0.0,
            ),
            PartModel(
                workshop_id=workshop_verified.id,
                name="Kit de embrague completo",
                description="Kit de embrague con disco, plato presión y release bearing, Chevrolet Onix 1.4",
                price=320.00,
                stock=3,
                condition="NEW",
                category="TRANSMISSION",
                allows_installments=1,
                installment_min_percentage=25.0,
            ),
            PartModel(
                workshop_id=workshop_verified.id,
                name="Bujías de iridio (juego 4)",
                description="Juego de 4 bujías de iridio NGK, compatibilidad universal para motores gasolina",
                price=28.00,
                stock=30,
                condition="NEW",
                category="ENGINE",
                allows_installments=0,
                installment_min_percentage=0.0,
            ),
            PartModel(
                workshop_id=workshop_verified.id,
                name="Amortiguadores delanteros",
                description="Par de amortiguadores delanteros gas, Ford Explorer 2016-2022",
                price=180.00,
                stock=6,
                condition="NEW",
                category="SUSPENSION",
                allows_installments=1,
                installment_min_percentage=30.0,
            ),
        ]
        for p in parts_verified:
            session.add(p)

        # ── PARTS (unverified workshop) ─────────────────────────

        parts_unverified = [
            PartModel(
                workshop_id=workshop_unverified.id,
                name="Neumático 205/55R16",
                description="Neumático todo tiempo 205/55R16, marca Pirelli, nuevo",
                price=95.00,
                stock=8,
                condition="NEW",
                category="OTHER",
                allows_installments=1,
                installment_min_percentage=15.0,
            ),
            PartModel(
                workshop_id=workshop_unverified.id,
                name="Limpiaparabrisas universales",
                description="Juego de 2 limpiaparabrisas universales, 24 pulgadas",
                price=8.50,
                stock=100,
                condition="NEW",
                category="CONSUMABLE",
                allows_installments=0,
                installment_min_percentage=0.0,
            ),
        ]
        for p in parts_unverified:
            session.add(p)

        await session.flush()
        print(
            f"[OK] {len(parts_verified)} repuestos (taller certificado) + {len(parts_unverified)} repuestos (taller no certificado) creados"
        )

        # ── USER PAYMENT ACCOUNTS ────────────────────────────────

        user_payment_accounts = [
            UserPaymentAccountModel(
                user_id=user1.id,
                account_type="BANK_TRANSFER",
                bank_name="Banesco",
                account_number="01021234567890123456",
                account_holder="Carlos Martínez",
                holder_document="V-12345678",
            ),
            UserPaymentAccountModel(
                user_id=user1.id,
                account_type="MOBILE_PAYMENT",
                bank_name="Mercantil Banco",
                phone_number="04121234567",
                holder_document="V-12345678",
            ),
            UserPaymentAccountModel(
                user_id=user2.id,
                account_type="BANK_TRANSFER",
                bank_name="Banco de Venezuela",
                account_number="01101234567890123456",
                account_holder="María Rodríguez",
                holder_document="V-23456789",
            ),
        ]
        for a in user_payment_accounts:
            session.add(a)
        await session.flush()
        print(f"[OK] {len(user_payment_accounts)} métodos de pago de usuario creados")

        # ── DONE ────────────────────────────────────────────────
        await session.commit()

    print()
    print("=" * 50)
    print("  Seed completado exitosamente")
    print("=" * 50)
    print(f"  user@example.com / {PASSWORD}  -> dueno de talleres, vehiculos, repuestos")
    print(f"  maria@example.com / {PASSWORD} -> compradora, solo vehiculos")
    print(f"  admin@example.com / {PASSWORD}  -> administrador del sistema")
    print(f"  gabrielsylar554@gmail.com / SUPER123* -> superadmin")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(seed())
