from neomodel import (
    StructuredNode, StringProperty, IntegerProperty, 
    RelationshipTo, RelationshipFrom, UniqueIdProperty, StructuredRel
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

class Editor(StructuredNode):
    """Editor of a publication or proceedings"""
    name = StringProperty(unique_index=True)
    # Could add ORCID or similar fields if available
    papers = RelationshipFrom('Paper', 'EDITED_BY')

class Paper(StructuredNode):
    """Paper node model."""
    doi = StringProperty(unique_index=True)
    title = StringProperty()
    year = StringProperty()
    source = StringProperty()
    volume = StringProperty()
    issue = StringProperty()
    pages = StringProperty()
    address = StringProperty()
    month = StringProperty()
    note = StringProperty()
    issn = StringProperty()
    isbn = StringProperty()
    url = StringProperty()
    language = StringProperty()
    type = StringProperty()
    abstract = StringProperty()
    copyright = StringProperty()

    # Relationships
    authors = RelationshipFrom('Author', 'AUTHORED')
    keywords = RelationshipTo('Keyword', 'HAS_KEYWORD')
    cited = RelationshipTo('Paper', 'CITED')
    references = RelationshipTo('Paper', 'REFERENCES')
    funders = RelationshipTo('Funder', 'FUNDED_BY')
    co_cited_with = RelationshipTo('Paper', 'CO_CITED_WITH', model=CoCitedRelationship)
    institutions = RelationshipTo('Institution', 'ASSOCIATED_WITH')

    publisher = RelationshipTo('Publisher', 'PUBLISHED_BY')
    editors = RelationshipTo('Editor', 'EDITED_BY')

class Author(StructuredNode):
    """Author node model."""
    name = StringProperty(unique_index=True)
    orcid = StringProperty(index=True)
    
    # Relationships
    papers = RelationshipTo('Paper', 'AUTHORED')
    institutions = RelationshipTo('Institution', 'AFFILIATED_WITH')

class Keyword(StructuredNode):
    """Keyword node model."""
    name = StringProperty(unique_index=True)
    
    # Relationships
    papers = RelationshipFrom('Paper', 'HAS_KEYWORD')

class Institution(StructuredNode):
    """Institution node model."""
    name = StringProperty(unique_index=True)
    
    # Relationships
    authors = RelationshipFrom('Author', 'AFFILIATED_WITH')

class Funder(StructuredNode):
    """Funder node model."""
    name = StringProperty(unique_index=True)
    doi = StringProperty(index=True)
    
    # Relationships
    papers = RelationshipFrom('Paper', 'FUNDED_BY')