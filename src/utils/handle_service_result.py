from fastapi import Response
from src.core.application.base_response import Response as BaseResponse


def handle_service_result(result: BaseResponse, response: Response) -> Response:
    if not result or not result.success:
        response.status_code = result.status_code
