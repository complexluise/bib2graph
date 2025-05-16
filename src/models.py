"""
Models module for bibliometric analysis of semiconductor supply chain.

This module defines the neomodel models for the entities used in the project.
"""

from neomodel import (
    StructuredNode, StringProperty, IntegerProperty, 
    RelationshipTo, RelationshipFrom, UniqueIdProperty, StructuredRel
)

class CoCitedRelationship(StructuredRel):
    """Relationship model for CO_CITED_WITH with properties."""
    weight = IntegerProperty()

class Paper(StructuredNode):
    """Paper node model."""
    doi = StringProperty(unique_index=True)
    title = StringProperty()
    year = StringProperty()
    source = StringProperty()
    
    # Relationships
    authors = RelationshipFrom('Author', 'AUTHORED')
    keywords = RelationshipTo('Keyword', 'HAS_KEYWORD')
    cited = RelationshipTo('Paper', 'CITED')
    references = RelationshipTo('Paper', 'REFERENCES')
    funders = RelationshipTo('Funder', 'FUNDED_BY')
    co_cited_with = RelationshipTo('Paper', 'CO_CITED_WITH', model=CoCitedRelationship)

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