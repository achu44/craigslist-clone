from django.db import models


class Flag(models.Model):
    """A community report against a posting."""

    posting = models.ForeignKey("postings.Posting", on_delete=models.CASCADE, related_name="flags")
    reason = models.CharField(max_length=255)
    reporter_fingerprint = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("posting", "reporter_fingerprint")]

    def __str__(self) -> str:
        return f"flag on {self.posting_id} by {self.reporter_fingerprint}"
