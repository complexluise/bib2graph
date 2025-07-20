from neomodel import (
    StructuredNode, StringProperty, IntegerProperty,
    RelationshipTo, RelationshipFrom, UniqueIdProperty, StructuredRel, BooleanProperty
)

class CoCitedRelationship(StructuredRel):
    """Relationship model for CO_CITED_WITH with properties."""
    weight = IntegerProperty()

class Publisher(StructuredNode):
    """Publisher node model."""
    name = StringProperty(unique_index=True)
    address = StringProperty()

    # Papers published
    papers = RelationshipFrom('Paper', 'PUBLISHED_BY')

class Paper(StructuredNode):
    """Paper node model."""
    doi = StringProperty(unique_index=True)
    title = StringProperty()
    year = StringProperty()
    source = StringProperty()
    volume = StringProperty()
    issue = StringProperty()
    pages = StringProperty()
    month = StringProperty()
    issn = StringProperty()
    isbn = StringProperty()
    url = StringProperty()
    language = StringProperty()
    type = StringProperty()
    abstract = StringProperty()
    is_seed = BooleanProperty()

    # Relationships
    authors = RelationshipFrom('Author', 'AUTHORED')
    keywords = RelationshipTo('Keyword', 'HAS_KEYWORD')
    research_areas = RelationshipTo('ResearchArea', 'RESEARCH_AREA')
    cited = RelationshipTo('Paper', 'CITED')
    references = RelationshipTo('Paper', 'REFERENCES')
    co_cited_with = RelationshipTo('Paper', 'CO_CITED_WITH', model=CoCitedRelationship)
    institutions = RelationshipTo('Institution', 'ASSOCIATED_WITH')

    publisher = RelationshipTo('Publisher', 'PUBLISHED_BY')

class Author(StructuredNode):
    """Author node model."""
    name = StringProperty(index=True)  # Ya no unique_index
    orcid = StringProperty(index=True)
    semantic_scholar_id = StringProperty(unique_index=True)  # Nuevo campo

    # Relationships
    papers = RelationshipTo('Paper', 'AUTHORED')
    institutions = RelationshipTo('Institution', 'AFFILIATED_WITH')

class Keyword(StructuredNode):
    """Keyword node model."""
    name = StringProperty(unique_index=True)

    # Relationships
    papers = RelationshipFrom('Paper', 'HAS_KEYWORD')

class ResearchArea(StructuredNode):
    name = StringProperty(unique_index=True)

    papers = RelationshipFrom('Paper', 'RESEARCH_AREA')

class Institution(StructuredNode):
    """Institution node model."""
    name = StringProperty(unique_index=True)

    # Relationships
    authors = RelationshipFrom('Author', 'AFFILIATED_WITH')
