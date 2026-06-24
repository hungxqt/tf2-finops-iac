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

class SecretsManagerClient:
    def get_secret_value(self, secret_id: str) -> str:
        raise NotImplementedError()

# Real AWS SDK Wrappers
class RealDynamoDB(DynamoDBClient):
    def __init__(self, client=None):
        self.client = client or boto3.client("dynamodb")

    def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # key format in boto3 DynamoDB is structured: {'key': {'S': 'value'}}
        # To make it simple and unified like our Go client, let's accept and return standard python dicts,
        # but wait, boto3 has a high level 'resource' Table or we can serialize/deserialize using boto3.dynamodb.types.
        # Let's check how our Go client did it: it converted attributes to maps.
        # In Python, we can do serialization/deserialization or use the boto3 DynamoDB resource Table which takes normal Python types.
        # Wait, does boto3 resource accept normal python types? Yes! The boto3 resource Table automatically handles normal dicts!
        # Let's implement RealDynamoDB using the high-level resource so we don't have to deal with attribute values like {'S': ...}!
        # But wait, does it matter? Yes, boto3.resource("dynamodb").Table(table_name) is much easier.
        # Let's use the standard boto3.resource("dynamodb").Table(table_name).
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

class RealSecretsManager(SecretsManagerClient):
    def __init__(self, client=None):
        self.client = client or boto3.client("secretsmanager")

    def get_secret_value(self, secret_id: str) -> str:
        response = self.client.get_secret_value(SecretId=secret_id)
        if "SecretString" in response:
            return response["SecretString"]
        return response["SecretBinary"].decode("utf-8")

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

    def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.get_item_func:
            return self.get_item_func(table_name, key)
        return None

    def put_item(self, table_name: str, item: Dict[str, Any]) -> None:
        if self.put_item_func:
            self.put_item_func(table_name, item)

    def update_item(self, table_name: str, key: Dict[str, Any], update_expression: str, expression_attribute_values: Dict[str, Any]) -> None:
        if self.update_item_func:
            self.update_item_func(table_name, key, update_expression, expression_attribute_values)

class FakeS3(S3Client):
    def __init__(
        self,
        put_object_func: Optional[Callable[[str, str, bytes], None]] = None,
        get_object_func: Optional[Callable[[str, str], bytes]] = None
    ):
        self.put_object_func = put_object_func
        self.get_object_func = get_object_func

    def put_object(self, bucket: str, key: str, body: bytes) -> None:
        if self.put_object_func:
            self.put_object_func(bucket, key, body)

    def get_object(self, bucket: str, key: str) -> bytes:
        if self.get_object_func:
            return self.get_object_func(bucket, key)
        return b""

class FakeSecretsManager(SecretsManagerClient):
    def __init__(self, get_secret_value_func: Optional[Callable[[str], str]] = None):
        self.get_secret_value_func = get_secret_value_func

    def get_secret_value(self, secret_id: str) -> str:
        if self.get_secret_value_func:
            return self.get_secret_value_func(secret_id)
        return ""
