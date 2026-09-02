import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Policy
from retrieval import find_matching_policy


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    session.add(
        Policy(
            name="Workplace Harassment Policy",
            description="Prohibits harassment and bullying.",
            category="Conduct",
            related_keywords="harassment, bullying, hostile, discrimination",
        )
    )
    session.add(
        Policy(
            name="Data Security Policy",
            description="Governs data handling.",
            category="Security",
            related_keywords="data breach, leak, password, phishing",
        )
    )
    session.commit()

    yield session
    session.close()


def test_finds_best_matching_policy(db):
    result = find_matching_policy(db, "My coworker sent a phishing email and leaked our data.")

    assert result is not None
    assert result.name == "Data Security Policy"


def test_returns_none_when_nothing_overlaps(db):
    result = find_matching_policy(db, "The office coffee machine is broken.")

    assert result is None


def test_returns_none_for_empty_text(db):
    result = find_matching_policy(db, "")

    assert result is None


def test_matches_on_category_and_name_too(db):
    # No related_keywords overlap, but "harassment" appears in the policy name.
    result = find_matching_policy(db, "There has been ongoing harassment in the team.")

    assert result is not None
    assert result.name == "Workplace Harassment Policy"
