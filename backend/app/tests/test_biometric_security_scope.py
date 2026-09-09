from unittest.mock import ANY, MagicMock

import pytest

from app.services.attendance_pipeline import stages
from app.services.attendance_pipeline.stages import MatchStageResult


def test_vector_matching_requires_organization_context():
    with pytest.raises(PermissionError, match="Organization context"):
        stages.match_by_vector(
            MagicMock(), embedding=[0.1] * 128, threshold=0.4,
            org_id=None, attendance_repo=MagicMock(),
        )


def test_vector_matching_passes_organization_to_repository():
    repository = MagicMock()
    repository.find_user_by_face.return_value = MagicMock(user_id=42)
    org_id = MagicMock()

    result = stages.match_by_vector(
        MagicMock(), embedding=[0.1] * 128, threshold=0.4,
        org_id=org_id, attendance_repo=repository,
    )

    assert result == MatchStageResult(matched_user_id=42)
    repository.find_user_by_face.assert_called_once_with(
        ANY, embedding=[0.1] * 128, threshold=0.4, org_id=org_id,
    )
