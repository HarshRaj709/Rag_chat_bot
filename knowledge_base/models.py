import uuid
from django.db import models
from common.models import BaseModel
from organization.models import Organisation
    

class KnowledgeBase(BaseModel):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="kbs")
    name = models.CharField(max_length=120)
    qdrant_collection = models.CharField(max_length=200, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.qdrant_collection:
            if not self.id:
                self.id = uuid.uuid4()
            self.qdrant_collection = f"kb_{self.id}"
        super().save(*args, **kwargs)


    class Meta:
        constraints = [
            models.UniqueConstraint(
            fields=['org', 'name'],
            name='unique_kb_name_per_org'
            )
        ]


class KBDocument(BaseModel):
    kb = models.ForeignKey(KnowledgeBase, on_delete=models.CASCADE, related_name="documents")
    filename = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=500)
    chunk_count = models.IntegerField(default=0)
    ingested_at = models.DateTimeField(null=True, blank=True)