from rest_framework import serializers
from django.db.models import Prefetch, Q

from pulseapi.issues.models import Issue
from pulseapi.profiles.models import (
    UserProfile,
    UserBookmarks,
)
from pulseapi.creators.models import OrderedCreatorRecord
from pulseapi.creators.serializers import EntryOrderedCreatorSerializer
from pulseapi.entries.models import Entry
from pulseapi.entries.serializers import EntryBaseSerializer, EntrySerializer


# Helper function to remove a value from a dictionary
# by key, removing the key itself as well.
def remove_key(data, key):
    try:
        del data[key]
    except:
        pass


class UserBookmarksSerializer(serializers.ModelSerializer):
    """
    Serializes a {user,entry,when} bookmark.
    """

    class Meta:
        """
        Meta class. Again: because
        """
        model = UserBookmarks


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializes a user profile.

    Note that the following fields should only show up when
    the 'enable_extended_information' flag is set to True:

    - user_bio_long
    - program_type
    - program_year
    - affiliation
    """
    profile_id = serializers.ReadOnlyField(source='id')

    custom_name = serializers.CharField(
        max_length=70,
        required=False,
        allow_blank=True,
    )
    location = serializers.CharField(
        max_length=1024,
        required=False,
        allow_blank=True,
    )
    thumbnail = serializers.ImageField(
        required=False,
        allow_null=True,
    )
    issues = serializers.SlugRelatedField(
        many=True,
        slug_field='name',
        queryset=Issue.objects,
        required=False
    )
    twitter = serializers.URLField(
        max_length=2048,
        required=False,
        allow_blank=True,
    )
    linkedin = serializers.URLField(
        max_length=2048,
        required=False,
        allow_blank=True,
    )
    github = serializers.URLField(
        max_length=2048,
        required=False,
        allow_blank=True,
    )
    website = serializers.URLField(
        max_length=2048,
        required=False,
        allow_blank=True,
    )

    user_bio = serializers.CharField(
        max_length=140,
        required=False,
        allow_blank=True,
    )

    profile_type = serializers.StringRelatedField()
    program_type = serializers.StringRelatedField()
    program_year = serializers.StringRelatedField()

    @staticmethod
    def trim_extended_information_from_dict(profile, profile_dict):
        if profile and profile.enable_extended_information is False:
            remove_key(profile_dict, 'user_bio_long')
            remove_key(profile_dict, 'program_type')
            remove_key(profile_dict, 'program_year')
            remove_key(profile_dict, 'affiliation')
        # Whether this flag is set or not, it should not
        # end up in the actual serialized profile data.
        remove_key(profile_dict, 'enable_extended_information')
        return profile_dict

    def to_representation(self, instance):
        serialized_profile = super().to_representation(instance)
        return UserProfileSerializer.trim_extended_information_from_dict(
            instance,
            serialized_profile
        )

    def update(self, instance, validated_data):
        validated_data = UserProfileSerializer.trim_extended_information_from_dict(
            instance,
            validated_data
        )
        return super(UserProfileSerializer, self).update(instance, validated_data)

    class Meta:
        """
        Meta class. Because
        """
        model = UserProfile
        read_only_fields = ('profile_type',)
        exclude = [
            'is_active',
            'bookmarks',
            'id',
            'is_group',
        ]


class UserProfilePublicSerializer(UserProfileSerializer):
    """
    Serializes a user profile for public view
    """
    name = serializers.CharField(read_only=True)
    my_profile = serializers.SerializerMethodField()

    def get_my_profile(self, instance):
        request = self.context.get('request')
        return request.user == instance.user if request else None


class UserProfilePublicWithEntriesSerializer(UserProfilePublicSerializer):
    """
    Serializes a user profile for public view and includes all entries
    associated with the profile
    """
    published_entries = serializers.SerializerMethodField()

    def get_published_entries(self, instance):
        user = instance.user

        return EntrySerializer(
            user.entries.public().with_related().order_by('-id'),
            context=self.context,
            many=True,
        ).data if user else []

    created_entries = serializers.SerializerMethodField()

    def get_created_entries(self, instance):
        entry_creator_records = OrderedCreatorRecord.objects.filter(creator__profile=instance).order_by('-id')
        return [EntrySerializer(x.entry).data for x in entry_creator_records if x.entry.is_approved()]


class UserProfileEntriesSerializer(serializers.Serializer):
    """
    Serializes entries related to a profile based on the requested
    entry types.

    Add any combination of the following parameters to the serializer context
    to request specific types of entries in the serialized data:
    - `created` - List of entries created by the profile
    - `published` - List of entries published by the profile
    - `favorited` - List of entries favorited/bookmarked by the profile

    If none of these parameters are passed in, this serializer falls back to
    returning the number of entries (created, published, and favorited) associated
    with the profile.
    """
    @staticmethod
    def serialize_entry(entry):
        serialized_entry = EntryBaseSerializer(entry).data
        serialized_entry['related_creators'] = EntryOrderedCreatorSerializer(
            entry.related_creators,
            many=True
        ).data
        return serialized_entry

    def to_representation(self, instance):
        data = {}
        context = self.context
        include_created = context.get('created', False)
        include_published = context.get('published', False)
        include_favorited = context.get('favorited', False)

        # If none of the filter options are provided, only return the count of
        # entries associated with this profile
        if not (include_created or include_published or include_favorited):
            entry_count = Entry.objects.public().filter(
                Q(related_creators__creator__profile=instance) |
                Q(published_by=instance.user) |
                Q(bookmarked_by__profile=instance)
            ).distinct().count()
            return {
                'entry_count': entry_count
            }

        entry_queryset = Entry.objects.prefetch_related(
            'related_creators__creator__profile__related_user'
        )

        if include_created:
            ordered_creators = (
                OrderedCreatorRecord.objects
                .prefetch_related(Prefetch('entry', queryset=entry_queryset))
                .filter(creator=instance.related_creator)
                .filter(entry__in=Entry.objects.public())
            )
            data['created'] = [
                self.serialize_entry(ordered_creator.entry)
                for ordered_creator in ordered_creators
            ]

        if include_published:
            entries = entry_queryset.public().filter(published_by=instance.user) if instance.user else []
            data['published'] = [self.serialize_entry(entry) for entry in entries]

        if include_favorited:
            user_bookmarks = UserBookmarks.objects.filter(profile=instance)
            data['favorited'] = [
                self.serialize_entry(bookmark.entry) for bookmark in
                user_bookmarks.prefetch_related(
                    Prefetch('entry', queryset=entry_queryset)
                ).filter(entry__in=Entry.objects.public())
            ]

        return data
