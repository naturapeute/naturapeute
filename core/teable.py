import json
import mimetypes
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


class TeableError(RuntimeError):
    """Raised when the Teable API rejects a request or cannot be reached."""


class TeableClient:
    def __init__(self, base_url, base_id, token, timeout=60):
        if not base_id:
            raise TeableError("TEABLE_BASE_ID is required")
        if not token:
            raise TeableError("TEABLE_API_TOKEN is required")
        self.base_url = base_url.rstrip("/")
        self.base_id = base_id
        self.token = token
        self.timeout = timeout

    def _request(self, method, path, query=None, payload=None, raw_body=None, content_type=None):
        url = f"{self.base_url}/api/{path.lstrip('/')}"
        if query:
            url = f"{url}?{urlencode(query, doseq=True)}"

        headers = {"Authorization": f"Bearer {self.token}"}
        body = raw_body
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif content_type:
            headers["Content-Type"] = content_type

        request = Request(url, data=body, headers=headers, method=method)
        for attempt in range(4):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    response_body = response.read()
                    if not response_body:
                        return {}
                    return json.loads(response_body.decode("utf-8"))
            except HTTPError as error:
                response_body = error.read().decode("utf-8", errors="replace")
                if error.code in {429, 500, 502, 503, 504} and attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise TeableError(
                    f"Teable API returned HTTP {error.code} for {method} {path}: "
                    f"{response_body[:500]}"
                ) from error
            except URLError as error:
                if attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise TeableError(f"Could not reach Teable API for {method} {path}: {error.reason}") from error

        raise TeableError(f"Teable API request failed for {method} {path}")

    def get_base(self):
        return self._request("GET", f"base/{self.base_id}")

    def list_tables(self):
        return self._request("GET", f"base/{self.base_id}/table")

    def create_table(self, name, db_table_name, fields, description=None, field_options=None):
        field_options = field_options or {}
        field_definitions = []
        for field_type, field_name, db_field_name in fields:
            field = {"type": field_type, "name": field_name, "dbFieldName": db_field_name}
            if field_name in field_options:
                field["options"] = field_options[field_name]
            field_definitions.append(field)
        payload = {
            "name": name,
            "dbTableName": db_table_name,
            "description": description,
            "fields": field_definitions,
        }
        return self._request("POST", f"base/{self.base_id}/table/", payload=payload)

    def list_fields(self, table_id):
        return self._request("GET", f"table/{table_id}/field")

    def create_field(self, table_id, field_type, field_name, db_field_name, options=None):
        payload = {
            "type": field_type,
            "name": field_name,
            "dbFieldName": db_field_name,
        }
        if options:
            payload["options"] = options
        return self._request("POST", f"table/{table_id}/field", payload=payload)

    def convert_field(self, table_id, field_id, field_type, field_name, db_field_name, options=None):
        payload = {
            "type": field_type,
            "name": field_name,
            "dbFieldName": db_field_name,
        }
        if options:
            payload["options"] = options
        return self._request(
            "PUT",
            f"table/{table_id}/field/{field_id}/convert",
            payload=payload,
        )

    def delete_field(self, table_id, field_id):
        return self._request("DELETE", f"table/{table_id}/field/{field_id}")

    def list_records(self, table_id, take=1000, skip=0):
        response = self._request(
            "GET",
            f"table/{table_id}/record",
            query={"fieldKeyType": "name", "take": take, "skip": skip},
        )
        if isinstance(response, dict):
            return response.get("records", [])
        return response

    def create_records(self, table_id, rows):
        if not rows:
            return []
        response = self._request(
            "POST",
            f"table/{table_id}/record",
            payload={
                "fieldKeyType": "name",
                "typecast": True,
                "records": [{"fields": row} for row in rows],
            },
        )
        if isinstance(response, dict):
            return response.get("records", [])
        return response

    def update_record(self, table_id, record_id, fields):
        return self._request(
            "PATCH",
            f"table/{table_id}/record/{record_id}",
            payload={"fieldKeyType": "name", "typecast": True, "record": {"fields": fields}},
        )

    def delete_record(self, table_id, record_id):
        return self._request("DELETE", f"table/{table_id}/record/{record_id}")

    def delete_records(self, table_id, record_ids):
        if not record_ids:
            return {}
        return self._request(
            "DELETE",
            f"table/{table_id}/record",
            query={"recordIds[]": record_ids},
        )

    def upload_attachment(self, table_id, record_id, field_id, file_path=None, file_url=None, filename=None):
        if not file_path and not file_url:
            raise TeableError("An attachment requires either a file path or a file URL")

        if file_url and not file_path:
            try:
                request = Request(
                    str(file_url),
                    headers={"User-Agent": "Naturapeute Teable importer"},
                )
                with urlopen(request, timeout=30) as response:
                    downloaded = response.read()
                remote_name = Path(urlparse(str(file_url)).path).name or "attachment"
                with tempfile.NamedTemporaryFile(
                    suffix=Path(remote_name).suffix or ".bin"
                ) as temporary:
                    temporary.write(downloaded)
                    temporary.flush()
                    return self.upload_attachment(
                        table_id,
                        record_id,
                        field_id,
                        file_path=temporary.name,
                        filename=remote_name,
                    )
            except (HTTPError, URLError, OSError):
                pass

        boundary = f"----teable-{uuid.uuid4().hex}"
        chunks = []
        if file_path:
            path = Path(file_path)
            filename = (filename or path.name).replace('"', "'")
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    (
                        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                        f"Content-Type: {content_type}\r\n\r\n"
                    ).encode(),
                    path.read_bytes(),
                    b"\r\n",
                ]
            )
        else:
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    b'Content-Disposition: form-data; name="fileUrl"\r\n\r\n',
                    str(file_url).encode("utf-8"),
                    b"\r\n",
                ]
            )
        chunks.append(f"--{boundary}--\r\n".encode())

        return self._request(
            "POST",
            f"table/{table_id}/record/{record_id}/{field_id}/uploadAttachment",
            raw_body=b"".join(chunks),
            content_type=f"multipart/form-data; boundary={boundary}",
        )
