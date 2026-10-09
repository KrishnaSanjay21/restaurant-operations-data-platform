from typing import Any

from restaurant_ops.socrata import SocrataClient


class FakeResponse:
    status_code = 200

    def __init__(self, payload: list[dict[str, Any]]) -> None:
        self._payload = payload
        self.text = "ok"

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict[str, Any]]:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def get(self, endpoint: str, params: dict[str, Any], timeout: int) -> FakeResponse:
        self.calls.append({"endpoint": endpoint, "params": params, "timeout": timeout})
        offset = int(params["$offset"])
        limit = int(params["$limit"])
        values = [{"id": str(index)} for index in range(offset, min(offset + limit, 5))]
        return FakeResponse(values)


def test_pagination_obeys_max_rows() -> None:
    session = FakeSession()
    client = SocrataClient(session=session)  # type: ignore[arg-type]
    pages = list(
        client.pages(
            source="test",
            endpoint="https://example.test/resource.json",
            columns="id",
            order_by="id",
            where=None,
            page_size=2,
            max_rows=5,
        )
    )
    assert [len(page.rows) for page in pages] == [2, 2, 1]
    assert sum(len(page.rows) for page in pages) == 5

