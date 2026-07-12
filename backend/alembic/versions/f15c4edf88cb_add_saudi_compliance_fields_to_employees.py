"""add_saudi_compliance_fields_to_employees

Revision ID: f15c4edf88cb
Revises: 5810624bd1be
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f15c4edf88cb'
down_revision: Union[str, Sequence[str], None] = '5810624bd1be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """إضافة حقول الامتثال لنظام العمل السعودي إلى جدول الموظفين."""
    op.add_column('employees', sa.Column('national_id', sa.String(length=16), nullable=True))
    op.add_column('employees', sa.Column('hire_date', sa.String(length=16), nullable=True))
    op.add_column('employees', sa.Column('basic_salary', sa.Float(), nullable=True))
    op.add_column('employees', sa.Column('housing_allowance', sa.Float(), nullable=True, server_default='0'))
    op.add_column('employees', sa.Column('other_allowances', sa.Float(), nullable=True, server_default='0'))
    op.add_column('employees', sa.Column('contract_type', sa.String(length=16), nullable=True, server_default='unlimited'))
    op.add_column('employees', sa.Column('contract_end_date', sa.String(length=16), nullable=True))
    op.add_column('employees', sa.Column('probation_end_date', sa.String(length=16), nullable=True))
    op.add_column('employees', sa.Column('gosi_registered_before_2024', sa.Boolean(), nullable=True, server_default='true'))


def downgrade() -> None:
    """التراجع عن حقول الامتثال."""
    op.drop_column('employees', 'gosi_registered_before_2024')
    op.drop_column('employees', 'probation_end_date')
    op.drop_column('employees', 'contract_end_date')
    op.drop_column('employees', 'contract_type')
    op.drop_column('employees', 'other_allowances')
    op.drop_column('employees', 'housing_allowance')
    op.drop_column('employees', 'basic_salary')
    op.drop_column('employees', 'hire_date')
    op.drop_column('employees', 'national_id')
