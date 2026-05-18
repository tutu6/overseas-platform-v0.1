"""集中导入所有模型,供 Alembic autogenerate 识别。"""
from app.db.models.user import User
from app.db.models.role import Role
from app.db.models.permission import Permission
from app.db.models.user_role import UserRole
from app.db.models.role_permission import RolePermission
from app.db.models.buyer_organization import BuyerOrganization
from app.db.models.supplier_organization import SupplierOrganization
from app.db.models.buyer_member import BuyerMember
from app.db.models.supplier_member import SupplierMember
from app.db.models.audit_log import AuditLog

__all__ = [
    "User",
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    "BuyerOrganization",
    "SupplierOrganization",
    "BuyerMember",
    "SupplierMember",
    "AuditLog",
]
