from django.shortcuts import get_object_or_404
from organization.models import Organisation


class GetOrgMixin:   
    def get_org(self):
        """
        Get the organization from the URL parameter 'pk' and cache it.
        
        Returns:
            Organisation: The organization object
            
        Raises:
            Http404: If organization with given pk doesn't exist
        """
        if not hasattr(self, "_org"):
            self._org = get_object_or_404(Organisation, pk=self.kwargs["pk"])
        return self._org
