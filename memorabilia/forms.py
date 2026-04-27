import json
import re

from django import forms
from django.forms import BaseInlineFormSet, ModelForm, CheckboxInput, ImageField, ModelChoiceField, ClearableFileInput, FileField, FilePathField, MultiValueField, inlineformset_factory

from django_flowbite_widgets.flowbite_fields import FlowbiteImageDropzoneField
from .models import (
    Collectible, Collection, PhotoMatch, League, GameType, UsageType, GearType,
    CoaType, AuthSource, HowObtainedOption, CollectibleImage,
    PlayerItem, PlayerItemImage, PlayerItemAuthentication,
    GeneralItem, GeneralItemImage, GeneralItemAuthentication,
    PlayerGear, PlayerGearImage, PlayerGearAuthentication,
    SeasonSet, HockeyJersey, UserProfile,
    WantListProfile, WantList, WantListItem, WantListItemImage,
    WANT_LIST_VISIBILITY_CHOICES,
)
from django.conf import settings
from django.core.files import File
from django.core.files.uploadedfile import InMemoryUploadedFile
import os
from django.core.files.storage import default_storage
from .widgets import FlickrAlbumWidget, ImageGallery
from django_flowbite_widgets import flowbite_widgets
from django.core.exceptions import PermissionDenied


class MultipleFileInput(ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class CollectionForm(ModelForm):
    header_image = FlowbiteImageDropzoneField(
        label=False,
        help_text="Upload a file or enter an image URL (optional)",
        required=False,
        file_field_name='image',
        url_field_name='image_link'
    )
    # Tracks which image option the user selected: 'current', 'new', or 'collage'
    image_mode = forms.CharField(widget=forms.HiddenInput(), required=False)
    # JSON list of {"type": ..., "id": ...} for user-picked collage images (>9 collectibles)
    collage_selection = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Collection
        fields = [
            "title",
            "allow_featured",
        ]
        labels = {
            "title": "Title",
            "allow_featured": "Allow items in this collection to be featured",
        }
        widgets = {
            "title": flowbite_widgets.FlowbiteTextInput(),
            "allow_featured": flowbite_widgets.FlowbiteCheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.collage_collectible_ids:
                self.initial['collage_selection'] = json.dumps(self.instance.collage_collectible_ids)
            if self.instance.get_header_image_url():
                self.initial['image_mode'] = 'current'
            else:
                self.initial['image_mode'] = 'collage'

    def clean_collage_selection(self):
        raw = self.cleaned_data.get('collage_selection', '').strip()
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            raise forms.ValidationError('Invalid collage selection data.')
        if not isinstance(data, list):
            raise forms.ValidationError('Invalid collage selection data.')
        if len(data) > 9:
            raise forms.ValidationError('Cannot select more than 9 images for the collage.')
        valid_types = {'playergear', 'playeritem', 'generalitem', 'hockeyjersey'}
        for entry in data:
            if not isinstance(entry, dict) or set(entry.keys()) != {'type', 'id'}:
                raise forms.ValidationError('Invalid collage selection data.')
            if entry['type'] not in valid_types:
                raise forms.ValidationError('Invalid collage selection data.')
            if not isinstance(entry['id'], int) or entry['id'] <= 0:
                raise forms.ValidationError('Invalid collage selection data.')
        return data

    def clean(self):
        cleaned_data = super().clean()
        mode = cleaned_data.get('image_mode') or 'current'
        header_image = cleaned_data.get('header_image')
        file_value, url_value = header_image if header_image else (None, None)

        if mode == 'new' and not file_value and not url_value:
            self.add_error('header_image', 'Please provide an image file or URL.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        mode = self.cleaned_data.get('image_mode') or 'current'
        header_image = self.cleaned_data.get('header_image')
        file_value, url_value = header_image if header_image else (None, None)

        if file_value:
            instance.image = file_value
            instance.image_link = None
        elif url_value:
            instance.image_link = url_value
            instance.image = None
        elif mode == 'collage':
            instance.image = None
            instance.image_link = None
            # clean_collage_selection already validated and parsed this to a list or None
            instance.collage_collectible_ids = self.cleaned_data.get('collage_selection') or None
        # else 'current' or 'new' (validation already enforced) → preserve existing

        if commit:
            instance.save()

        return instance


HOW_OBTAINED_SEPARATOR = '──── Users ────'

ALLOW_FEATURED_CHOICES = [
    ('', 'Use collection setting'),
    ('true', 'Yes – allow'),
    ('false', 'No – do not allow'),
]


class HowObtainedValidationMixin:
    def clean_how_obtained(self):
        value = self.cleaned_data.get('how_obtained', '') or ''
        if value.strip() == HOW_OBTAINED_SEPARATOR:
            raise forms.ValidationError('Please select a valid value.')
        return value.strip()


class CollectibleForm(HowObtainedValidationMixin, ModelForm):
    league = forms.CharField(
        required=False,
        widget=flowbite_widgets.FlowbiteTextInput(),
        help_text="Select from the list or type a custom value",
    )
    allow_featured = forms.TypedChoiceField(
        label='Allow to be featured',
        choices=ALLOW_FEATURED_CHOICES,
        coerce=lambda v: None if v == '' else (v == 'true'),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput(),
    )

    class Meta:
        model = PlayerItem
        fields = "__all__"
        exclude = ['for_sale', 'for_trade', 'looking_for', 'asking_price', 'images', 'collectible_type', 'flickr_url']
        widgets = {
            "title": flowbite_widgets.FlowbiteTextInput(),
            "player": flowbite_widgets.FlowbiteTextInput(),
            "team": flowbite_widgets.FlowbiteTextInput(),
            "asking_price": flowbite_widgets.FlowbiteTextInput(),
            "number": flowbite_widgets.FlowbiteNumberInput(),
            "collection": flowbite_widgets.FlowbiteSelectInput(),
            "looking_for": flowbite_widgets.FlowbiteSelectInput(),
            "for_sale": flowbite_widgets.FlowbiteCheckboxInput(),
            "for_trade": flowbite_widgets.FlowbiteCheckboxInput(),
            "description": flowbite_widgets.FlowbiteTextarea(),
            "how_obtained": flowbite_widgets.FlowbiteTextInput(),
        }


    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        self.fields['collection'].queryset = Collection.objects.filter(owner_uid=self.current_user.id)
        # Enable browser suggestions for league via datalist rendered in the template
        self.fields['league'].widget.attrs.update({
            'list': 'league-list',
            'placeholder': 'e.g., NHL, AHL, NCAA, custom...'
        })
        # Enable browser suggestions for team via datalist rendered in the template
        self.fields['team'].widget.attrs.update({
            'list': 'team-list',
            'placeholder': 'Start typing a team...'
        })
        self.fields['how_obtained'].widget.attrs.update({
            'list': 'how-obtained-list',
            'placeholder': 'Select or type how this was obtained...'
        })
        val = self.instance.allow_featured if (self.instance and self.instance.pk) else self.initial.get('allow_featured')
        self.initial['allow_featured'] = 'true' if val is True else ('false' if val is False else '')
        self.fields['allow_featured'] = self.fields.pop('allow_featured')

    def get_image_fields(self):
        for field_name in self.fields:
            if field_name.startswith("image_"):
                yield self[field_name]

    def clean_league(self):
        value = self.cleaned_data.get("league", "")
        return value.strip()


class CollectibleImageForm(ModelForm):

    # images = ImageGallery(required=False)

    class Meta:
        model = PlayerItemImage
        fields = "__all__"
        widgets = {
            # "image": flowbite_widgets.FlowbiteTextInput(),
            "link": flowbite_widgets.FlowbiteTextInput(),
            "primary": flowbite_widgets.FlowbiteCheckboxInput(),
            "flickrObject": flowbite_widgets.FlowbiteTextarea(),
        }


class GeneralItemImageForm(ModelForm):
    """Form for GeneralItem images"""
    class Meta:
        model = GeneralItemImage
        fields = "__all__"
        widgets = {
            "link": flowbite_widgets.FlowbiteTextInput(),
            "primary": flowbite_widgets.FlowbiteCheckboxInput(),
            "flickrObject": flowbite_widgets.FlowbiteTextarea(),
        }


class GeneralItemForm(HowObtainedValidationMixin, ModelForm):
    """Form for GeneralItem - contains only base Collectible fields"""
    allow_featured = forms.TypedChoiceField(
        label='Allow to be featured',
        choices=ALLOW_FEATURED_CHOICES,
        coerce=lambda v: None if v == '' else (v == 'true'),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput(),
    )

    class Meta:
        model = GeneralItem
        fields = "__all__"
        exclude = ['for_sale', 'for_trade', 'looking_for', 'asking_price', 'images', 'flickr_url']
        widgets = {
            "title": flowbite_widgets.FlowbiteTextInput(),
            "collection": flowbite_widgets.FlowbiteSelectInput(),
            "description": flowbite_widgets.FlowbiteTextarea(),
            "how_obtained": flowbite_widgets.FlowbiteTextInput(),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        self.fields['collection'].queryset = Collection.objects.filter(owner_uid=self.current_user.id)
        self.fields['how_obtained'].widget.attrs.update({
            'list': 'how-obtained-list',
            'placeholder': 'Select or type how this was obtained...'
        })
        val = self.instance.allow_featured if (self.instance and self.instance.pk) else self.initial.get('allow_featured')
        self.initial['allow_featured'] = 'true' if val is True else ('false' if val is False else '')
        self.fields['allow_featured'] = self.fields.pop('allow_featured')


class PlayerGearImageForm(ModelForm):
    """Form for PlayerGear images"""
    class Meta:
        model = PlayerGearImage
        fields = "__all__"
        widgets = {
            "link": flowbite_widgets.FlowbiteTextInput(),
            "primary": flowbite_widgets.FlowbiteCheckboxInput(),
            "flickrObject": flowbite_widgets.FlowbiteTextarea(),
        }


class PlayerGearForm(HowObtainedValidationMixin, ModelForm):
    """Form for PlayerGear - includes all PlayerItem fields plus gear-specific fields"""
    league = forms.CharField(
        required=True,
        widget=flowbite_widgets.FlowbiteTextInput(),
        help_text="Select from the list or type a custom value",
    )
    game_type = ModelChoiceField(
        queryset=GameType.objects.all(),
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    usage_type = ModelChoiceField(
        queryset=UsageType.objects.all(),
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    gear_type = ModelChoiceField(
        queryset=GearType.objects.all(),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    allow_featured = forms.TypedChoiceField(
        label='Allow to be featured',
        choices=ALLOW_FEATURED_CHOICES,
        coerce=lambda v: None if v == '' else (v == 'true'),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput(),
    )

    class Meta:
        model = PlayerGear
        fields = "__all__"
        exclude = ['for_sale', 'for_trade', 'looking_for', 'asking_price', 'images', 'season_set', 'home_away', 'flickr_url']
        widgets = {
            "title": flowbite_widgets.FlowbiteTextInput(),
            "brand": flowbite_widgets.FlowbiteTextInput(),
            "size": flowbite_widgets.FlowbiteTextInput(),
            "player": flowbite_widgets.FlowbiteTextInput(),
            "team": flowbite_widgets.FlowbiteTextInput(),
            "season": flowbite_widgets.FlowbiteTextInput(),
            "number": flowbite_widgets.FlowbiteNumberInput(),
            "collection": flowbite_widgets.FlowbiteSelectInput(),
            "description": flowbite_widgets.FlowbiteTextarea(),
            "how_obtained": flowbite_widgets.FlowbiteTextInput(),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        self.fields['collection'].queryset = Collection.objects.filter(owner_uid=self.current_user.id)
        self.fields['league'].widget.attrs.update({
            'list': 'league-list',
            'placeholder': 'e.g., NHL, AHL, NCAA, custom...'
        })
        self.fields['team'].widget.attrs.update({
            'list': 'team-list',
            'placeholder': 'Start typing a team...'
        })
        self.fields['how_obtained'].widget.attrs.update({
            'list': 'how-obtained-list',
            'placeholder': 'Select or type how this was obtained...'
        })
        val = self.instance.allow_featured if (self.instance and self.instance.pk) else self.initial.get('allow_featured')
        self.initial['allow_featured'] = 'true' if val is True else ('false' if val is False else '')
        self.fields['allow_featured'] = self.fields.pop('allow_featured')

    def clean_league(self):
        return self.cleaned_data.get("league", "").strip()


class HockeyJerseyForm(PlayerGearForm):
    """Form for HockeyJersey - all PlayerGear fields plus season_set; gear_type is auto-set."""
    gear_type = ModelChoiceField(
        queryset=GearType.objects.all(),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    season_set = ModelChoiceField(
        queryset=SeasonSet.objects.all(),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    home_away = forms.ChoiceField(
        choices=[('', '---------')] + list(PlayerGear.HOME_AWAY_CHOICES),
        required=False,
        label='Home/Away',
        widget=flowbite_widgets.FlowbiteSelectInput(),
    )

    class Meta(PlayerGearForm.Meta):
        model = HockeyJersey
        exclude = ['for_sale', 'for_trade', 'looking_for', 'asking_price', 'images', 'flickr_url']
        widgets = PlayerGearForm.Meta.widgets


def get_collectible_form_class(collectible_type='PlayerItem'):
    """Factory function to get the appropriate form class based on type"""
    if collectible_type == 'GeneralItem':
        return GeneralItemForm
    if collectible_type == 'PlayerGear':
        return PlayerGearForm
    if collectible_type == 'HockeyJersey':
        return HockeyJerseyForm
    return CollectibleForm


class CustomCollectibleImageFormSet(BaseInlineFormSet):
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs.update({'empty_permitted': False})
        return kwargs
    
    def add_fields(self, form, index):
        super().add_fields(form, index)
        if self.can_delete:
            form.fields['DELETE'].widget = flowbite_widgets.FlowbiteCheckboxInput(attrs={
                'data-index': index,
            })

    def clean(self):
        super().clean()
        primary_count = 0
        non_deleted_count = 0
        for form in self.forms:
            # Skip forms that didn't validate to cleaned_data
            if not hasattr(form, 'cleaned_data'):
                continue
            # Ignore deleted forms
            if self.can_delete and form.cleaned_data.get('DELETE'):
                continue
            non_deleted_count += 1
            # Count primary selections
            if form.cleaned_data.get('primary'):
                primary_count += 1
        # If there are no images, allow without error
        if non_deleted_count == 0:
            return
        if primary_count != 1:
            raise forms.ValidationError("Select exactly one primary image.")


CollectibleImageFormSet = inlineformset_factory(
    # Collectible,
    # CollectibleImage, 
    PlayerItem,
    PlayerItemImage,
    form=CollectibleImageForm,
    formset=CustomCollectibleImageFormSet,
    extra=0,
    can_delete=True,
    # min_num=0,
    # validate_min=True,
    # max_num=10,
    # validate_max=True
)

PlayerGearImageFormSet = inlineformset_factory(
    PlayerGear,
    PlayerGearImage,
    form=PlayerGearImageForm,
    formset=CustomCollectibleImageFormSet,
    fk_name='collectible',
    extra=0,
    can_delete=True,
)

def _fetch_getty_thumbnail(embed_code):
    import requests
    match = re.search(r"items:'(\d+)'", embed_code)
    if not match:
        return None
    asset_id = match.group(1)
    try:
        resp = requests.get(
            f'https://embed.gettyimages.com/oembed?url=https://www.gettyimages.com/detail/{asset_id}',
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json().get('thumbnail_url')
    except Exception:
        return None


class PhotoMatchForm(ModelForm):

    photo = FlowbiteImageDropzoneField(
        label="Photo",
        help_text="Enter an image URL or upload a file",
        file_field_name='image',
        url_field_name='link'
    )

    getty_embed_code = forms.CharField(
        required=False,
        label="Getty Embed Code",
        help_text="Paste the embed code from Getty Images",
        widget=flowbite_widgets.FlowbiteTextarea(attrs={'rows': 4, 'placeholder': "Paste the embed code from Getty Images here"}),
    )

    class Meta:
        model = PhotoMatch
        fields = ["collectible", "game_date", "description"]
        widgets = {
            "collectible": flowbite_widgets.FlowbiteSelectInput(),
            "game_date": flowbite_widgets.FlowbiteTextInput(),
            "description": flowbite_widgets.FlowbiteTextarea(),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['photo'].initial = (self.instance.image, self.instance.link)
            if self.instance.getty_embed_code:
                self.fields['getty_embed_code'].initial = self.instance.getty_embed_code

    def clean(self):
        cleaned_data = super().clean()
        photo = cleaned_data.get('photo') or (None, None)
        file_value, url_value = photo
        getty_code = cleaned_data.get('getty_embed_code', '')
        # Preserve existing photo on edit — only require a new one when creating
        has_existing = self.instance and self.instance.pk and (
            self.instance.image or self.instance.link or self.instance.getty_embed_code
        )
        if not file_value and not url_value and not getty_code and not has_existing:
            self.add_error('photo', 'Please add a photo by uploading a file, pasting a URL, or entering a Getty embed code.')
        return cleaned_data

    def clean_getty_embed_code(self):
        value = self.cleaned_data.get('getty_embed_code', '').strip()
        if not value:
            return ''
        if 'gettyimages.com' not in value:
            raise forms.ValidationError('Please paste a valid Getty Images embed code.')
        return value

    def save(self, commit=True):
        pm = super().save(commit=False)

        file_value, url_value = self.cleaned_data.get('photo') or (None, None)
        getty_code = self.cleaned_data.get('getty_embed_code', '')

        if file_value:
            pm.image = file_value
            pm.link = None
            pm.getty_embed_code = None
        elif url_value:
            pm.link = url_value
            pm.image = None
            pm.getty_embed_code = None
        elif getty_code:
            pm.getty_embed_code = getty_code
            pm.image = None
            pm.link = None
            # Only re-fetch thumbnail if the embed code changed
            if getty_code != getattr(self.instance, 'getty_embed_code', None):
                pm.getty_thumbnail_url = _fetch_getty_thumbnail(getty_code)
        # else: no new photo provided — preserve existing values on the instance

        if commit:
            pm.save()
        
        
class CollectibleSearchForm(forms.Form):
    query = forms.CharField(required=False, label="Text", widget=flowbite_widgets.FlowbiteTextInput())
    player = forms.CharField(required=False, label="Player", widget=flowbite_widgets.FlowbiteTextInput())
    team = forms.CharField(required=False, label="Team", widget=flowbite_widgets.FlowbiteTextInput())
    brand = forms.CharField(required=False, label="Brand", widget=flowbite_widgets.FlowbiteTextInput())
    number = forms.IntegerField(required=False, label="Number", widget=flowbite_widgets.FlowbiteTextInput())
    season = forms.CharField(required=False, label="Season", widget=flowbite_widgets.FlowbiteTextInput())
    league = forms.CharField(required=False, label="League", widget=flowbite_widgets.FlowbiteTextInput())
    game_type = forms.ChoiceField(required=False, label="Game Type", choices=[], widget=flowbite_widgets.FlowbiteSelectInput)
    usage_type = forms.ChoiceField(required=False, label="Usage Type", choices=[], widget=flowbite_widgets.FlowbiteSelectInput)
    collection = forms.ChoiceField(required=False, label="Collection", choices=[], widget=flowbite_widgets.FlowbiteSelectInput)
    for_sale = forms.ChoiceField(
        required=False,
        label="For Sale",
        choices=[('', 'Any'), ('true', 'Yes'), ('false', 'No')],
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    for_trade = forms.ChoiceField(
        required=False,
        label="For Trade",
        choices=[('', 'Any'), ('true', 'Yes'), ('false', 'No')],
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    item_type = forms.ChoiceField(
        required=False,
        label="Item Type",
        choices=[
            ('', 'Any'),
            ('generalitem', 'General Item'),
            ('hockeyjersey', 'Hockey Jersey'),
            ('playergear', 'Player Gear'),
            ('playeritem', 'Player Item'),
        ],
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    season_set = forms.ChoiceField(required=False, label="Season Set", choices=[], widget=flowbite_widgets.FlowbiteSelectInput)
    gear_type = forms.ChoiceField(required=False, label="Gear Type", choices=[], widget=flowbite_widgets.FlowbiteSelectInput)
    home_away = forms.ChoiceField(
        required=False,
        label="Home/Away",
        choices=[('', 'Any'), ('H', 'Home'), ('A', 'Away')],
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    auth_issuer = forms.ChoiceField(required=False, label="Authentication Issuer", choices=[], widget=flowbite_widgets.FlowbiteSelectInput)
    auth_number = forms.CharField(required=False, label="Authentication #", widget=flowbite_widgets.FlowbiteTextInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Enable browser suggestions for league via datalist rendered in the template
        self.fields['league'].widget.attrs.update({
            'list': 'league-list',
            'placeholder': 'e.g., NHL, AHL, NCAA, custom...'
        })
        # Enable browser suggestions for team via datalist rendered in the template
        self.fields['team'].widget.attrs.update({
            'list': 'team-list',
            'placeholder': 'Start typing a team...'
        })
        self.fields['game_type'].choices = [('', '')] + [(g.key, g.name) for g in GameType.objects.all()]
        self.fields['usage_type'].choices = [('', '')] + [(u.key, u.name) for u in UsageType.objects.all()]
        self.fields['collection'].choices = [('', 'Any')] + [(c.id, c.title) for c in Collection.objects.all()]
        self.fields['season_set'].choices = [('', '')] + [(s.key, s.name) for s in SeasonSet.objects.all()]
        self.fields['gear_type'].choices = [('', '')] + [(g.key, g.name) for g in GearType.objects.all()]
        self.fields['auth_issuer'].choices = [('', 'Any')] + [(a.key, a.name) for a in AuthSource.objects.all()]


class BulkCollectibleForm(ModelForm):
    """Simplified form for bulk editing PlayerItems in a formset."""

    allow_featured = forms.TypedChoiceField(
        label='Allow to be featured',
        choices=ALLOW_FEATURED_CHOICES,
        coerce=lambda v: None if v == '' else (v == 'true'),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput(),
    )

    class Meta:
        model = PlayerItem
        fields = ['title', 'description', 'how_obtained', 'league', 'player', 'team', 'number', 'allow_featured']
        widgets = {
            'title': flowbite_widgets.FlowbiteTextInput(),
            'league': flowbite_widgets.FlowbiteTextInput(),
            'player': flowbite_widgets.FlowbiteTextInput(),
            'team': flowbite_widgets.FlowbiteTextInput(),
            'how_obtained': flowbite_widgets.FlowbiteTextInput(attrs={'list': 'how-obtained-list', 'placeholder': 'Select or type how this was obtained...'}),
            'description': flowbite_widgets.FlowbiteTextarea(attrs={'rows': 2}),
            'number': flowbite_widgets.FlowbiteNumberInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['league'].widget.attrs.update({
            'placeholder': 'e.g., NHL, AHL, NCAA, custom...'
        })
        self.fields['team'].widget.attrs.update({
            'placeholder': 'Start typing a team...'
        })
        val = self.instance.allow_featured if (self.instance and self.instance.pk) else None
        self.initial['allow_featured'] = 'true' if val is True else ('false' if val is False else '')


class BulkPlayerGearForm(ModelForm):
    """Simplified form for bulk editing PlayerGear items in a formset."""

    game_type = ModelChoiceField(queryset=GameType.objects.all(), widget=flowbite_widgets.FlowbiteSelectInput)
    usage_type = ModelChoiceField(queryset=UsageType.objects.all(), widget=flowbite_widgets.FlowbiteSelectInput)
    gear_type = ModelChoiceField(queryset=GearType.objects.all(), required=False, widget=flowbite_widgets.FlowbiteSelectInput)
    number = forms.IntegerField(required=False, widget=flowbite_widgets.FlowbiteNumberInput())
    allow_featured = forms.TypedChoiceField(
        label='Allow to be featured',
        choices=ALLOW_FEATURED_CHOICES,
        coerce=lambda v: None if v == '' else (v == 'true'),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput(),
    )

    class Meta:
        model = PlayerGear
        fields = ['title', 'description', 'how_obtained', 'league', 'player', 'team', 'number', 'brand', 'size', 'season', 'game_type', 'usage_type', 'gear_type', 'allow_featured']
        widgets = {
            'title': flowbite_widgets.FlowbiteTextInput(),
            'league': flowbite_widgets.FlowbiteTextInput(),
            'player': flowbite_widgets.FlowbiteTextInput(),
            'team': flowbite_widgets.FlowbiteTextInput(),
            'brand': flowbite_widgets.FlowbiteTextInput(),
            'size': flowbite_widgets.FlowbiteTextInput(),
            'season': flowbite_widgets.FlowbiteTextInput(),
            'how_obtained': flowbite_widgets.FlowbiteTextInput(attrs={'list': 'how-obtained-list', 'placeholder': 'Select or type how this was obtained...'}),
            'description': flowbite_widgets.FlowbiteTextarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['league'].widget.attrs.update({'placeholder': 'e.g., NHL, AHL...'})
        self.fields['team'].widget.attrs.update({'placeholder': 'Start typing a team...'})
        val = self.instance.allow_featured if (self.instance and self.instance.pk) else None
        self.initial['allow_featured'] = 'true' if val is True else ('false' if val is False else '')


class BulkHockeyJerseyForm(ModelForm):
    """Simplified form for bulk editing HockeyJersey items in a formset."""
    game_type = ModelChoiceField(queryset=GameType.objects.all(), widget=flowbite_widgets.FlowbiteSelectInput)
    usage_type = ModelChoiceField(queryset=UsageType.objects.all(), widget=flowbite_widgets.FlowbiteSelectInput)
    gear_type = ModelChoiceField(queryset=GearType.objects.all(), required=False, widget=flowbite_widgets.FlowbiteSelectInput)
    season_set = ModelChoiceField(queryset=SeasonSet.objects.all(), required=False, widget=flowbite_widgets.FlowbiteSelectInput)
    number = forms.IntegerField(required=False, widget=flowbite_widgets.FlowbiteNumberInput())
    home_away = forms.ChoiceField(
        choices=[('', '---------')] + list(PlayerGear.HOME_AWAY_CHOICES),
        required=False,
        label='Home/Away',
        widget=flowbite_widgets.FlowbiteSelectInput(),
    )
    allow_featured = forms.TypedChoiceField(
        label='Allow to be featured',
        choices=ALLOW_FEATURED_CHOICES,
        coerce=lambda v: None if v == '' else (v == 'true'),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput(),
    )

    class Meta:
        model = HockeyJersey
        fields = ['title', 'description', 'how_obtained', 'league', 'player', 'team', 'number', 'brand', 'size', 'season', 'game_type', 'usage_type', 'gear_type', 'season_set', 'home_away', 'allow_featured']
        widgets = {
            'title': flowbite_widgets.FlowbiteTextInput(),
            'league': flowbite_widgets.FlowbiteTextInput(),
            'player': flowbite_widgets.FlowbiteTextInput(),
            'team': flowbite_widgets.FlowbiteTextInput(),
            'brand': flowbite_widgets.FlowbiteTextInput(),
            'size': flowbite_widgets.FlowbiteTextInput(),
            'season': flowbite_widgets.FlowbiteTextInput(),
            'how_obtained': flowbite_widgets.FlowbiteTextInput(attrs={'list': 'how-obtained-list', 'placeholder': 'Select or type how this was obtained...'}),
            'description': flowbite_widgets.FlowbiteTextarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['league'].widget.attrs.update({'placeholder': 'e.g., NHL, AHL...'})
        self.fields['team'].widget.attrs.update({'placeholder': 'Start typing a team...'})
        val = self.instance.allow_featured if (self.instance and self.instance.pk) else None
        self.initial['allow_featured'] = 'true' if val is True else ('false' if val is False else '')


class BulkGeneralItemForm(ModelForm):
    """Simplified form for bulk editing GeneralItems in a formset."""

    allow_featured = forms.TypedChoiceField(
        label='Allow to be featured',
        choices=ALLOW_FEATURED_CHOICES,
        coerce=lambda v: None if v == '' else (v == 'true'),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput(),
    )

    class Meta:
        model = GeneralItem
        fields = ['title', 'description', 'how_obtained', 'allow_featured']
        widgets = {
            'title': flowbite_widgets.FlowbiteTextInput(),
            'how_obtained': flowbite_widgets.FlowbiteTextInput(attrs={'list': 'how-obtained-list', 'placeholder': 'Select or type how this was obtained...'}),
            'description': flowbite_widgets.FlowbiteTextarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        val = self.instance.allow_featured if (self.instance and self.instance.pk) else None
        self.initial['allow_featured'] = 'true' if val is True else ('false' if val is False else '')


class AuthenticationForm(ModelForm):
    auth_type = ModelChoiceField(
        queryset=CoaType.objects.all(),
        required=False,
        label='Type',
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    issuer = ModelChoiceField(
        queryset=AuthSource.objects.all(),
        required=False,
        label='Issuer',
        widget=flowbite_widgets.FlowbiteSelectInput,
    )

    class Meta:
        fields = ['auth_type', 'number', 'issuer']
        widgets = {
            'number': flowbite_widgets.FlowbiteTextInput(),
        }


class PlayerGearAuthenticationForm(AuthenticationForm):
    class Meta(AuthenticationForm.Meta):
        model = PlayerGearAuthentication


class PlayerItemAuthenticationForm(AuthenticationForm):
    class Meta(AuthenticationForm.Meta):
        model = PlayerItemAuthentication


class GeneralItemAuthenticationForm(AuthenticationForm):
    class Meta(AuthenticationForm.Meta):
        model = GeneralItemAuthentication


PlayerGearAuthenticationFormSet = inlineformset_factory(
    PlayerGear,
    PlayerGearAuthentication,
    form=PlayerGearAuthenticationForm,
    extra=0,
    can_delete=True,
)

PlayerItemAuthenticationFormSet = inlineformset_factory(
    PlayerItem,
    PlayerItemAuthentication,
    form=PlayerItemAuthenticationForm,
    extra=0,
    can_delete=True,
)

GeneralItemAuthenticationFormSet = inlineformset_factory(
    GeneralItem,
    GeneralItemAuthentication,
    form=GeneralItemAuthenticationForm,
    extra=0,
    can_delete=True,
)


class UserProfileForm(ModelForm):
    class Meta:
        model = UserProfile
        fields = ['flickr_id']
        widgets = {
            'flickr_id': flowbite_widgets.FlowbiteTextInput(attrs={'placeholder': 'e.g. 12345678@N04'}),
        }
        labels = {
            'flickr_id': 'Flickr User ID',
        }
        help_texts = {
            'flickr_id': 'Your Flickr NSID (e.g. 12345678@N04). Used to pre-fill album imports.',
        }


# ── Want List Forms ────────────────────────────────────────────────────────────

_RESERVED_WANT_LIST_SLUGS = {'manage', 'me', 'new', 'edit', 'delete', 'create', 'profile', 'api', 'admin'}


class WantListProfileForm(ModelForm):
    header_image = FlowbiteImageDropzoneField(
        label='Header Image',
        help_text='Upload a file or enter an image URL (optional)',
        required=False,
        file_field_name='header_image',
        url_field_name='header_image_link',
    )

    class Meta:
        model = WantListProfile
        fields = ['slug', 'visibility']
        widgets = {
            'slug': flowbite_widgets.FlowbiteTextInput(attrs={'placeholder': 'e.g., jamie-witt'}),
            'visibility': flowbite_widgets.FlowbiteSelectInput(),
        }
        labels = {
            'slug': 'Public URL handle',
            'visibility': 'Who can see your want list',
        }
        help_texts = {
            'slug': 'Letters, numbers, and hyphens only. This becomes your public URL.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['header_image'].initial = (
                self.instance.header_image,
                self.instance.header_image_link,
            )

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').lower().strip()
        if slug in _RESERVED_WANT_LIST_SLUGS:
            raise forms.ValidationError('That handle is reserved. Please choose another.')
        return slug

    def save(self, commit=True):
        instance = super().save(commit=False)
        file_value, url_value = self.cleaned_data.get('header_image') or (None, None)
        if file_value:
            instance.header_image = file_value
            instance.header_image_link = None
        elif url_value:
            instance.header_image_link = url_value
            instance.header_image = None
        if commit:
            instance.save()
        return instance


class WantListForm(ModelForm):
    class Meta:
        model = WantList
        fields = ['title']
        widgets = {
            'title': flowbite_widgets.FlowbiteTextInput(),
        }


class WantListItemForm(ModelForm):
    want_list = ModelChoiceField(
        queryset=WantList.objects.none(),
        widget=flowbite_widgets.FlowbiteSelectInput(),
        empty_label='— Select list —',
        label='Want List',
    )
    league = ModelChoiceField(
        queryset=League.objects.all(),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput(),
        empty_label='— Select league —',
    )
    game_type = ModelChoiceField(
        queryset=GameType.objects.all(),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    usage_type = ModelChoiceField(
        queryset=UsageType.objects.all(),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    gear_type = ModelChoiceField(
        queryset=GearType.objects.all(),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput,
    )
    season_set = ModelChoiceField(
        queryset=SeasonSet.objects.all(),
        required=False,
        widget=flowbite_widgets.FlowbiteSelectInput,
    )

    class Meta:
        model = WantListItem
        fields = [
            'want_list', 'collectible_type', 'league', 'player', 'team', 'number',
            'season', 'game_type', 'usage_type', 'gear_type', 'season_set',
            'title', 'description', 'notes',
        ]
        widgets = {
            'collectible_type': flowbite_widgets.FlowbiteSelectInput(),
            'player': flowbite_widgets.FlowbiteTextInput(),
            'team': flowbite_widgets.FlowbiteTextInput(),
            'number': flowbite_widgets.FlowbiteNumberInput(),
            'season': flowbite_widgets.FlowbiteTextInput(),
            'title': flowbite_widgets.FlowbiteTextInput(),
            'description': flowbite_widgets.FlowbiteTextarea(),
            'notes': flowbite_widgets.FlowbiteTextarea(),
        }
        labels = {
            'title': 'Title',
            'description': 'Description',
        }

    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user')
        super().__init__(*args, **kwargs)
        self.fields['want_list'].queryset = WantList.objects.filter(profile__user=current_user)
        self.fields['team'].widget.attrs.update({
            'list': 'team-list',
            'placeholder': 'Start typing a team...',
        })

    def clean(self):
        cleaned_data = super().clean()
        descriptive_fields = [
            'player', 'team', 'number', 'season', 'league',
            'game_type', 'usage_type', 'gear_type', 'season_set',
            'title', 'description', 'notes',
        ]
        if not any(cleaned_data.get(f) for f in descriptive_fields):
            raise forms.ValidationError('Please fill in at least one field describing the item.')
        return cleaned_data


class WantListItemImageForm(ModelForm):
    class Meta:
        model = WantListItemImage
        fields = ['image', 'link']
        widgets = {
            'link': flowbite_widgets.FlowbiteTextInput(attrs={'placeholder': 'Or paste an image URL...'}),
        }
        labels = {
            'link': 'Image URL',
        }


WantListItemImageFormSet = inlineformset_factory(
    WantListItem,
    WantListItemImage,
    form=WantListItemImageForm,
    extra=3,
    can_delete=True,
    max_num=3,
    validate_max=True,
)