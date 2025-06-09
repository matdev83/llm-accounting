# API Key Encryption Feature Implementation Plan

## Overview
This document outlines the implementation plan for adding secure API key storage functionality to the llm-accounting package. The feature will use AWS KMS for encryption and secure in-memory enclaves for temporary key storage.

## Goals
- Provide secure storage for LLM API keys
- Support multiple LLM providers (OpenAI, Anthropic, etc.)
- Maintain backward compatibility
- Follow existing codebase patterns and practices
- Ensure proper security measures

## Implementation Steps

### 1. Dependencies
Add new dependencies to `pyproject.toml`:
```toml
[tool.poetry.dependencies]
boto3 = "^1.34.0"  # For AWS KMS integration
```

### 2. New Module Structure

src/llm_accounting/
├── key_management/
│ ├── init.py
│ ├── secure_key_manager.py
│ ├── exceptions.py
│ └── models.py
```

### 3. Core Components

#### 3.1 Key Management Models
`src/llm_accounting/key_management/models.py`:
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class APIKeyRecord:
    service_name: str
    user_id: Optional[str]
    created_at: datetime
    last_used: Optional[datetime]
    is_active: bool = True
```

#### 3.2 Secure Key Manager
`src/llm_accounting/key_management/secure_key_manager.py`:
```python
from typing import Optional, Dict
import boto3
from botocore.exceptions import ClientError
import logging
import os
from datetime import datetime, timedelta
from .models import APIKeyRecord

logger = logging.getLogger(__name__)

class SecureKeyManager:
    def __init__(
        self,
        kms_key_id: str,
        region_name: str = "us-east-1",
        cache_ttl: int = 3600
    ):
        self.kms = boto3.client('kms', region_name=region_name)
        self.kms_key_id = kms_key_id
        self.cache_ttl = cache_ttl
        self._key_cache: Dict[str, tuple[str, datetime]] = {}
        
    def store_api_key(self, service_name: str, api_key: str, user_id: Optional[str] = None) -> None:
        try:
            response = self.kms.encrypt(
                KeyId=self.kms_key_id,
                Plaintext=api_key.encode(),
                EncryptionContext={
                    'service': service_name,
                    'user_id': user_id or 'global'
                }
            )
            
            # Store encrypted key in the backend
            self._store_encrypted_key(service_name, user_id, response['CiphertextBlob'])
            
        except ClientError as e:
            logger.error(f"Failed to encrypt API key: {e}")
            raise
            
    def get_api_key(self, service_name: str, user_id: Optional[str] = None) -> Optional[str]:
        key_id = f"{service_name}_{user_id or 'global'}"
        
        # Check cache
        if key_id in self._key_cache:
            key, expiry = self._key_cache[key_id]
            if datetime.now() < expiry:
                return key
            del self._key_cache[key_id]
        
        try:
            encrypted_key = self._retrieve_encrypted_key(service_name, user_id)
            if not encrypted_key:
                return None
                
            response = self.kms.decrypt(
                CiphertextBlob=encrypted_key,
                KeyId=self.kms_key_id,
                EncryptionContext={
                    'service': service_name,
                    'user_id': user_id or 'global'
                }
            )
            
            decrypted_key = response['Plaintext'].decode()
            expiry = datetime.now() + timedelta(seconds=self.cache_ttl)
            self._key_cache[key_id] = (decrypted_key, expiry)
            
            return decrypted_key
            
        except ClientError as e:
            logger.error(f"Failed to decrypt API key: {e}")
            return None
```

#### 3.3 Backend Integration
Add to `src/llm_accounting/backends/base.py`:
```python
class BaseBackend(ABC):
    # ... existing methods ...
    
    @abstractmethod
    def store_encrypted_key(self, service_name: str, user_id: Optional[str], encrypted_key: bytes) -> None:
        """Store an encrypted API key."""
        pass
        
    @abstractmethod
    def get_encrypted_key(self, service_name: str, user_id: Optional[str]) -> Optional[bytes]:
        """Retrieve an encrypted API key."""
        pass
```

### 4. LLMAccounting Integration

Update `src/llm_accounting/__init__.py`:
```python
class LLMAccounting:
    def __init__(
        self,
        backend: Optional[BaseBackend] = None,
        project_name: Optional[str] = None,
        app_name: Optional[str] = None,
        user_name: Optional[str] = None,
        audit_backend: Optional[BaseBackend] = None,
        enforce_project_names: bool = False,
        enforce_user_names: bool = False,
        key_manager: Optional[SecureKeyManager] = None,
    ):
        # ... existing initialization ...
        self.key_manager = key_manager or SecureKeyManager(
            kms_key_id=os.environ.get("LLM_ACCOUNTING_KMS_KEY_ID"),
            region_name=os.environ.get("AWS_REGION", "us-east-1")
        )
        
    def store_api_key(self, service_name: str, api_key: str) -> None:
        """Store an API key for a service."""
        self.key_manager.store_api_key(service_name, api_key, self.user_name)
        
    def get_api_key(self, service_name: str) -> Optional[str]:
        """Get an API key for a service."""
        return self.key_manager.get_api_key(service_name, self.user_name)
```

### 5. CLI Integration

Add new commands to `src/llm_accounting/cli/commands/`:
```python
# keys.py
def add_keys_parser(subparsers):
    keys_parser = subparsers.add_parser(
        "keys", help="Manage API keys for LLM services"
    )
    keys_subparsers = keys_parser.add_subparsers(
        dest="keys_command", help="Keys commands", required=True
    )
    
    # Store key command
    store_parser = keys_subparsers.add_parser("store", help="Store an API key")
    store_parser.add_argument(
        "--service",
        type=str,
        required=True,
        help="Service name (e.g., openai, anthropic)"
    )
    store_parser.add_argument(
        "--key",
        type=str,
        required=True,
        help="API key to store"
    )
    
    # List keys command
    list_parser = keys_subparsers.add_parser("list", help="List stored API keys")
    list_parser.add_argument(
        "--service",
        type=str,
        help="Filter by service name"
    )
```

### 6. Database Schema Updates

Add to `alembic/versions/`:
```python
"""add_api_keys_table

Revision ID: xxx
Revises: previous_revision
Create Date: 2024-xx-xx

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_name', sa.String(255), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=True),
        sa.Column('encrypted_key', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service_name', 'user_id')
    )

def downgrade():
    op.drop_table('api_keys')
```

### 7. Testing

Create test files:
```
tests/
├── key_management/
│   ├── __init__.py
│   ├── test_secure_key_manager.py
│   └── test_integration.py
```

Example test:
```python
# tests/key_management/test_secure_key_manager.py
import pytest
from unittest.mock import MagicMock, patch
from llm_accounting.key_management.secure_key_manager import SecureKeyManager

@pytest.fixture
def mock_kms():
    with patch('boto3.client') as mock:
        yield mock

def test_store_api_key(mock_kms):
    manager = SecureKeyManager(kms_key_id='test-key')
    manager.store_api_key('openai', 'test-key', 'user1')
    # Add assertions
```

### 8. Documentation

Update `README.md` with new sections:
```markdown
## API Key Management

The package now supports secure storage of API keys for various LLM services.

### Configuration

1. Set up AWS KMS:
```bash
# Create a KMS key
aws kms create-key --description "LLM Accounting API Keys"
aws kms create-alias --alias-name alias/llm-accounting-keys --target-key-id <key-id>
```

2. Configure environment variables:
```bash
export LLM_ACCOUNTING_KMS_KEY_ID="arn:aws:kms:region:account:key/key-id"
export AWS_REGION="us-east-1"
```

### Usage

```python
from llm_accounting import LLMAccounting

# Initialize with key management
accounting = LLMAccounting()

# Store an API key
accounting.store_api_key("openai", "sk-...")

# Use the API key
api_key = accounting.get_api_key("openai")
```

### CLI Usage

```bash
# Store an API key
llm-accounting keys store --service openai --key sk-...

# List stored keys
llm-accounting keys list
```
```

## Security Considerations

1. **KMS Key Management**
   - Use appropriate IAM permissions
   - Enable key rotation
   - Monitor usage through CloudTrail

2. **In-Memory Security**
   - Implement proper cache TTL
   - Clear memory on application exit
   - Handle memory securely

3. **Access Control**
   - Implement proper user authentication
   - Use encryption context
   - Log all key access

## Migration Plan

1. **Phase 1: Development**
   - Implement core functionality
   - Add tests
   - Update documentation

2. **Phase 2: Testing**
   - Internal testing
   - Security review
   - Performance testing

3. **Phase 3: Release**
   - Version bump
   - Release notes
   - Documentation updates

## Future Enhancements

1. Support for additional KMS providers (Azure, GCP)
2. Key rotation automation
3. Usage analytics for API keys
4. Integration with existing quota system
```

Would you like me to make any adjustments to the content before you create/update the file?