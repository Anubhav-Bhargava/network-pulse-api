"""
Views to get entries
"""

import django_filters
from rest_framework import (filters, status)
from rest_framework.decorators import detail_route, api_view
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView, ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from pulseapi.entries.models import Entry
from pulseapi.entries.serializers import EntrySerializer
from pulseapi.users.models import UserBookmarks

@api_view(['PUT'])
def toggle_bookmark(request, entryid):
    """
    Toggle whether or not this user "bookmarked" the url-indicated entry.
    This is currently defined outside of the entry class, as functionality
    that is technically independent of entries themselves. We might
    change this in the future.
    """
    user = request.user

    if user.is_authenticated():
        entry = None

        # find the entry for this id
        try:
            entry = Entry.objects.get(id=entryid)
        except Entry.DoesNotExist:
            return Response("No such entry", status=status.HTTP_404_NOT_FOUND)

        # find is there is already a {user,entry,(timestamp)} triple
        bookmarks = entry.bookmarked_by.filter(user=user)
        exists = bookmarks.count() > 0

        # if there is a bookmark, remove it. Otherwise, make one.
        if exists:
            for bookmark in bookmarks:
                bookmark.delete()
        else:
            bookmark = UserBookmarks(entry=entry, user=user)
            bookmark.save()

        return Response("Toggled bookmark.", status=status.HTTP_204_NO_CONTENT)
    return Response("Anonymous bookmarks cannot be saved.", status=status.HTTP_403_FORBIDDEN)

def post_validate(request):
    """
    Security helper function to ensure that a post request is session, CSRF, and nonce protected
    """
    user = request.user
    csrf_token = False
    nonce = False

    if request.data:
        csrf_token = request.data.get('csrfmiddlewaretoken', False)
        nonce = request.data.get('nonce', False)
    else:
        csrf_token = request.POST.get('csrfmiddlewaretoken', False)
        nonce = request.POST.get('nonce', False)

    # ignore post attempts without a CSRF token
    if csrf_token is False:
        return "No CSRF token in POST data."

    # ignore post attempts without a known form id
    if nonce is False:
        return "No form identifier in POST data."

    # ignore post attempts by clients that are not logged in
    if not user.is_authenticated:
        return "Anonymous posting is not supported."

    # ignore unexpected post attempts (i.e. missing the session-based unique form id)
    if nonce != request.session['nonce']:
        # invalidate the nonce entirely, so people can't retry until there's an id collision
        request.session['nonce'] = False
        return "Forms cannot be auto-resubmitted (e.g. by reloading)."

    return True

class EntriesPagination(PageNumberPagination):
    """
    Add support for pagination and custom page size
    """
    # page size decided in https://github.com/mozilla/network-pulse-api/issues/39
    page_size = 48
    page_size_query_param = 'page_size'
    max_page_size = 1000

class EntryCustomFilter(filters.FilterSet):
    """
    We add custom filtering to allow you to filter by:
        * Tag - pass the `?tag=` query parameter
        * Issue - pass the `?issue=` query parameter
        * Featured - `?featured=True` (or False) - both capitalied
    Accepts only one filter value i.e. one tag and/or one
    category.
    """
    tag = django_filters.CharFilter(
        name='tags__name',
        lookup_expr='iexact',
    )
    issue = django_filters.CharFilter(
        name='issues__name',
        lookup_expr='iexact',
    )
    featured = django_filters.BooleanFilter(
        name='featured'
    )

    class Meta:
        """
        Required Meta class
        """
        model = Entry
        fields = ['tags', 'issues', 'featured',]


class EntryView(RetrieveAPIView):
    """
    A view to retrieve individual entries
    """
    queryset = Entry.objects.public()
    serializer_class = EntrySerializer
    pagination_class = None


class BookmarkedEntries(ListAPIView):

    def get_queryset(self):
        entries = set()
        user = self.request.user.id
        for bookmark in UserBookmarks.objects.filter(user=user).select_related('entry'):
            entries.add(bookmark.entry)
        return entries

    serializer_class = EntrySerializer

class EntriesListView(ListCreateAPIView):
    """
    A view that permits a GET to allow listing all the entries
    in the database

    **Route** - `/entries`

    #Query Parameters -

    - `?search=` - Allows search terms
    - `?tag=` - Allows filtering entries by a specific tag
    - `?issue=` - Allows filtering entries by a specific issue
    - `?featured=True` (or False) - both capitalied. Boolean is set in admin UI
    - `?page=` - Page number, defaults to 1
    - `?page_size=` - Number of results on a page. Defaults to 48
    """
    queryset = Entry.objects.public()
    pagination_class = EntriesPagination
    filter_backends = (
        filters.DjangoFilterBackend,
        filters.SearchFilter,
    )
    filter_class = EntryCustomFilter
    search_fields = (
        'title',
        'description',
    )
    serializer_class = EntrySerializer

    # When people POST to this route, we want to do some
    # custom validation involving CSRF and nonce validation,
    # so we intercept the POST handling a little.
    @detail_route(methods=['post'])
    def post(self, request, *args, **kwargs):
        validation_result = post_validate(request)
        if validation_result is True:
            # invalidate the nonce, so this form cannot be resubmitted with the current id
            request.session['nonce'] = False

            serializer = EntrySerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(published_by=request.user)
                return Response({'status': 'submitted'})
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response("post validation failed", status=status.HTTP_400_BAD_REQUEST)
