from __future__ import annotations

from typing import Any, Dict, Optional

import logging

import requests

logger = logging.getLogger(__name__)


class InternalAPIError(RuntimeError):
    """Base error for internal API client failures."""


class NotFoundError(InternalAPIError):
    """Resource was not found (HTTP 404)."""


class ConflictError(InternalAPIError):
    """Request could not be applied because of a conflict (HTTP 409)."""


class ServerError(InternalAPIError):
    """Server returned a 5xx error."""


class InternalAPIClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        default_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if default_headers:
            self.session.headers.update(default_headers)

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        timeout = kwargs.pop("timeout", self.timeout)
        try:
            response = self.session.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            raise InternalAPIError(f"Request to {url} failed: {exc}") from exc

        if response.status_code == 404:
            raise NotFoundError(response.text or f"Resource at {path} not found")
        if response.status_code == 409:
            raise ConflictError(response.text or f"Conflict when calling {path}")
        if 400 <= response.status_code < 500:
            raise InternalAPIError(
                f"Client error {response.status_code} for {method} {path}: {response.text}"
            )
        if 500 <= response.status_code:
            raise ServerError(
                f"Server error {response.status_code} for {method} {path}: {response.text}"
            )
        if response.status_code == 204:
            return None
        if response.content:
            try:
                return response.json()
            except ValueError as exc:
                raise InternalAPIError(
                    f"Non-JSON response for {method} {path}: {response.text}"
                ) from exc
        return None

    # --- Audio job helpers -------------------------------------------------
    def claim_audio_job(self, job_id: int) -> Dict[str, Any]:
        return self._request("POST", f"/audio-jobs/{job_id}/claim")

    def update_audio_job(
        self,
        job_id: int,
        *,
        status: str,
        output_path: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"status": status}
        if output_path is not None:
            payload["output_path"] = output_path
        if error is not None:
            payload["error"] = error
        return self._request("PATCH", f"/audio-jobs/{job_id}", json=payload)

    def mark_audio_job_failed(self, job_id: int, error: Optional[str]) -> Dict[str, Any]:
        payload = {"error": error}
        return self._request("POST", f"/audio-jobs/{job_id}/fail", json=payload)

    # --- Dialogue helpers --------------------------------------------------
    def set_dialogue_audio(self, dialogue_id: int, audio_path: str) -> None:
        payload = {"audio_path": audio_path}
        self._request("PATCH", f"/dialogues/{dialogue_id}/audio", json=payload)

    def set_dialogue_status(self, dialogue_id: int, status: str) -> None:
        payload = {"status": status}
        self._request("PATCH", f"/dialogues/{dialogue_id}/status", json=payload)

    # --- Project helpers ---------------------------------------------------
    def get_project(self, project_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}")

    def get_project_dialogues(self, project_id: int, status: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if status:
            params["status"] = status
        return self._request("GET", f"/projects/{project_id}/dialogues", params=params)

    def get_ready_assets(self, project_id: int) -> Optional[list[Dict[str, Any]]]:
        return self._request("GET", f"/projects/{project_id}/ready-assets")

    def transition_status(self, project_id: int, expected: str, new_status: str) -> Dict[str, Any]:
        payload = {"expected": expected, "next": new_status}
        return self._request("POST", f"/projects/{project_id}/status-transition", json=payload)

    def get_completion_counts(self, project_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/projects/{project_id}/completion")

    def set_video_path(self, project_id: int, video_path: str) -> None:
        payload = {"video_path": video_path}
        self._request("PATCH", f"/projects/{project_id}/video-path", json=payload)
