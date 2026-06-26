import boto3
from typing import Dict, Any, Optional, Callable

# Interfaces / Base classes
class DynamoDBClient:
    def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError()

    def put_item(self, table_name: str, item: Dict[str, Any]) -> None:
        raise NotImplementedError()

    def update_item(self, table_name: str, key: Dict[str, Any], update_expression: str, expression_attribute_values: Dict[str, Any]) -> None:
        raise NotImplementedError()

class S3Client:
    def put_object(self, bucket: str, key: str, body: bytes) -> None:
        raise NotImplementedError()

    def get_object(self, bucket: str, key: str) -> bytes:
        raise NotImplementedError()

    def list_objects_v2(self, bucket: str, prefix: str) -> Dict[str, Any]:
        raise NotImplementedError()

class SecretsManagerClient:
    def get_secret_value(self, secret_id: str) -> str:
        raise NotImplementedError()

class CostExplorerClient:
    def get_cost_and_usage(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError()

class CloudWatchClient:
    def get_metric_data(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError()

class STSClient:
    def assume_role(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError()

    def get_caller_identity(self) -> Dict[str, Any]:
        raise NotImplementedError()

# Real AWS SDK Wrappers
class RealDynamoDB(DynamoDBClient):
    def __init__(self, client=None):
        self.client = client or boto3.client("dynamodb")

    def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        db = boto3.resource("dynamodb")
        table = db.Table(table_name)
        response = table.get_item(Key=key)
        return response.get("Item")

    def put_item(self, table_name: str, item: Dict[str, Any]) -> None:
        db = boto3.resource("dynamodb")
        table = db.Table(table_name)
        table.put_item(Item=item)

    def update_item(self, table_name: str, key: Dict[str, Any], update_expression: str, expression_attribute_values: Dict[str, Any]) -> None:
        db = boto3.resource("dynamodb")
        table = db.Table(table_name)
        table.update_item(
            Key=key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values
        )

class RealS3(S3Client):
    def __init__(self, client=None):
        self.client = client or boto3.client("s3")

    def put_object(self, bucket: str, key: str, body: bytes) -> None:
        self.client.put_object(Bucket=bucket, Key=key, Body=body)

    def get_object(self, bucket: str, key: str) -> bytes:
        response = self.client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def list_objects_v2(self, bucket: str, prefix: str) -> Dict[str, Any]:
        return self.client.list_objects_v2(Bucket=bucket, Prefix=prefix)

class RealSecretsManager(SecretsManagerClient):
    def __init__(self, client=None):
        self.client = client or boto3.client("secretsmanager")

    def get_secret_value(self, secret_id: str) -> str:
        response = self.client.get_secret_value(SecretId=secret_id)
        if "SecretString" in response:
            return response["SecretString"]
        return response["SecretBinary"].decode("utf-8")

class RealCostExplorer(CostExplorerClient):
    def __init__(self, client=None):
        self.client = client or boto3.client("ce")

    def get_cost_and_usage(self, **kwargs) -> Dict[str, Any]:
        return self.client.get_cost_and_usage(**kwargs)

class RealCloudWatch(CloudWatchClient):
    def __init__(self, client=None):
        self.client = client or boto3.client("cloudwatch")

    def get_metric_data(self, **kwargs) -> Dict[str, Any]:
        return self.client.get_metric_data(**kwargs)

class RealSTS(STSClient):
    def __init__(self, client=None):
        self.client = client or boto3.client("sts")

    def assume_role(self, **kwargs) -> Dict[str, Any]:
        return self.client.assume_role(**kwargs)

    def get_caller_identity(self) -> Dict[str, Any]:
        return self.client.get_caller_identity()

# Fake client mock implementations
class FakeDynamoDB(DynamoDBClient):
    def __init__(
        self,
        get_item_func: Optional[Callable[[str, Dict[str, Any]], Optional[Dict[str, Any]]]] = None,
        put_item_func: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        update_item_func: Optional[Callable[[str, Dict[str, Any], str, Dict[str, Any]], None]] = None
    ):
        self.get_item_func = get_item_func
        self.put_item_func = put_item_func
        self.update_item_func = update_item_func
        # Isolate items by table name to prevent cross-table collisions
        self.items: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.get_item_func:
            return self.get_item_func(table_name, key)
        # Use table-isolated storage
        table_items = self.items.get(table_name, {})
        key_str = str(sorted(key.items()))
        return table_items.get(key_str)

    def put_item(self, table_name: str, item: Dict[str, Any], condition_expression: Optional[str] = None) -> None:
        if self.put_item_func:
            self.put_item_func(table_name, item)
            return
        # Use table-isolated storage
        if table_name not in self.items:
            self.items[table_name] = {}
        # Extract key from item (assume first key in item dict is the hash key)
        key = {k: v for k, v in item.items() if k in ["idempotency_key", "tenant_id", "anomaly_id"]}
        key_str = str(sorted(key.items()))
        
        # Handle conditional put
        if condition_expression and "attribute_not_exists" in condition_expression:
            if key_str in self.items[table_name]:
                raise ValueError("ConditionalCheckFailedException: Item already exists")
        
        self.items[table_name][key_str] = item

    def update_item(self, table_name: str, key: Dict[str, Any], update_expression: str, expression_attribute_values: Dict[str, Any]) -> None:
        if self.update_item_func:
            self.update_item_func(table_name, key, update_expression, expression_attribute_values)

class FakeS3(S3Client):
    def __init__(
        self,
        put_object_func: Optional[Callable[[str, str, bytes], None]] = None,
        get_object_func: Optional[Callable[[str, str], bytes]] = None,
        list_objects_func: Optional[Callable[[str, str], Dict[str, Any]]] = None
    ):
        self.put_object_func = put_object_func
        self.get_object_func = get_object_func
        self.list_objects_func = list_objects_func

    def put_object(self, bucket: str, key: str, body: bytes) -> None:
        if self.put_object_func:
            self.put_object_func(bucket, key, body)

    def get_object(self, bucket: str, key: str) -> bytes:
        if self.get_object_func:
            return self.get_object_func(bucket, key)
        return b""

    def list_objects_v2(self, bucket: str, prefix: str) -> Dict[str, Any]:
        if self.list_objects_func:
            return self.list_objects_func(bucket, prefix)
        return {}

class FakeSecretsManager(SecretsManagerClient):
    def __init__(self, get_secret_value_func: Optional[Callable[[str], str]] = None):
        self.get_secret_value_func = get_secret_value_func

    def get_secret_value(self, secret_id: str) -> str:
        if self.get_secret_value_func:
            return self.get_secret_value_func(secret_id)
        return ""

class FakeCostExplorer(CostExplorerClient):
    def __init__(self, get_cost_and_usage_func: Optional[Callable[..., Dict[str, Any]]] = None):
        self.get_cost_and_usage_func = get_cost_and_usage_func

    def get_cost_and_usage(self, **kwargs) -> Dict[str, Any]:
        if self.get_cost_and_usage_func:
            return self.get_cost_and_usage_func(**kwargs)
        return {}

class FakeCloudWatch(CloudWatchClient):
    def __init__(self, get_metric_data_func: Optional[Callable[..., Dict[str, Any]]] = None):
        self.get_metric_data_func = get_metric_data_func

    def get_metric_data(self, **kwargs) -> Dict[str, Any]:
        if self.get_metric_data_func:
            return self.get_metric_data_func(**kwargs)
        return {}

class FakeSTS(STSClient):
    def __init__(
        self,
        assume_role_func: Optional[Callable[..., Dict[str, Any]]] = None,
        get_caller_identity_func: Optional[Callable[..., Dict[str, Any]]] = None
    ):
        self.assume_role_func = assume_role_func
        self.get_caller_identity_func = get_caller_identity_func

    def assume_role(self, **kwargs) -> Dict[str, Any]:
        if self.assume_role_func:
            return self.assume_role_func(**kwargs)
        return {
            "Credentials": {
                "AccessKeyId": "fake-access-key",
                "SecretAccessKey": "fake-secret-key",
                "SessionToken": "fake-session-token",
                "Expiration": "2026-06-26T12:00:00Z"
            }
        }

    def get_caller_identity(self) -> Dict[str, Any]:
        if self.get_caller_identity_func:
            return self.get_caller_identity_func()
        return {"AccountId": "112233445566", "Arn": "arn:aws:iam::112233445566:role/test-role"}
