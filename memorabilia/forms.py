import json

from django import forms
from django.forms import BaseInlineFormSet, ModelForm, CheckboxInput, ImageField, ModelChoiceField, ClearableFileInput, FileField, FilePathField, MultiValueField, inlineformset_factory

from django_flowbite_widgets.flowbite_fields import FlowbiteImageDropzoneField
from .models import Collectible, Collection, PhotoMatch, League, GameType, UsageType, CollectibleImage, PlayerItem, PlayerItemImage, OtherItem, OtherItemImage, PlayerGearItem, PlayerGearItemImage
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
        ]
        labels = {
            "title": "Title",
        }
        widgets = {
            "title": flowbite_widgets.FlowbiteTextInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.collage_collectible_ids:
            self.initial['collage_selection'] = json.dumps(self.instance.collage_collectible_ids)

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
        valid_types = {'playergearitem', 'playeritem', 'otheritem'}
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


class CollectibleForm(ModelForm):
    league = forms.CharField(
        required=False,
        widget=flowbite_widgets.FlowbiteTextInput(),
        help_text="Select from the list or type a custom value",
    )

    class Meta:
        model = PlayerItem
        fields = "__all__"
        exclude = ['for_sale', 'for_trade', 'looking_for', 'asking_price', 'images', 'collectible_type']
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


class OtherItemImageForm(ModelForm):
    """Form for OtherItem images"""
    class Meta:
        model = OtherItemImage
        fields = "__all__"
        widgets = {
            "link": flowbite_widgets.FlowbiteTextInput(),
            "primary": flowbite_widgets.FlowbiteCheckboxInput(),
            "flickrObject": flowbite_widgets.FlowbiteTextarea(),
        }


class OtherItemForm(ModelForm):
    """Form for OtherItem - contains only base Collectible fields"""
    class Meta:
        model = OtherItem
        fields = "__all__"
        exclude = ['for_sale', 'for_trade', 'looking_for', 'asking_price', 'images']
        widgets = {
            "title": flowbite_widgets.FlowbiteTextInput(),
            "collection": flowbite_widgets.FlowbiteSelectInput(),
            "description": flowbite_widgets.FlowbiteTextarea(),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        self.fields['collection'].queryset = Collection.objects.filter(owner_uid=self.current_user.id)


class PlayerGearItemImageForm(ModelForm):
    """Form for PlayerGearItem images"""
    class Meta:
        model = PlayerGearItemImage
        fields = "__all__"
        widgets = {
            "link": flowbite_widgets.FlowbiteTextInput(),
            "primary": flowbite_widgets.FlowbiteCheckboxInput(),
            "flickrObject": flowbite_widgets.FlowbiteTextarea(),
        }


class PlayerGearItemForm(ModelForm):
    """Form for PlayerGearItem - includes all PlayerItem fields plus gear-specific fields"""
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

    class Meta:
        model = PlayerGearItem
        fields = "__all__"
        exclude = ['for_sale', 'for_trade', 'looking_for', 'asking_price', 'images']
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

    def clean_league(self):
        return self.cleaned_data.get("league", "").strip()


def get_collectible_form_class(collectible_type='PlayerItem'):
    """Factory function to get the appropriate form class based on type"""
    if collectible_type == 'OtherItem':
        return OtherItemForm
    if collectible_type == 'PlayerGearItem':
        return PlayerGearItemForm
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

PlayerGearItemImageFormSet = inlineformset_factory(
    PlayerGearItem,
    PlayerGearItemImage,
    form=PlayerGearItemImageForm,
    formset=CustomCollectibleImageFormSet,
    fk_name='collectible',
    extra=0,
    can_delete=True,
)


class PhotoMatchForm(ModelForm):

    photo = FlowbiteImageDropzoneField(
        label="Photo",
        help_text="Enter an image URL or upload a file",
        # required=False,
        # max_file_size=5*1024*1024,  # 2MB
        # allowed_extensions=['jpg', 'jpeg', 'png']
        file_field_name='image',
        url_field_name='link'
    )


    class Meta:
        model = PhotoMatch
        fields = ["collectible", "game_date", "description"]
        widgets = {
            "collectible": flowbite_widgets.FlowbiteSelectInput(),
            "game_date": flowbite_widgets.FlowbiteTextInput(),
            # "image": flowbite_widgets.FlowbiteImageDropzone(),
            # "link": flowbite_widgets.FlowbiteTextInput(),
            "description": flowbite_widgets.FlowbiteTextarea(),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        # self.fields['photomatch'].queryset = PhotoMatch.objects.filter(owner_uid=self.current_user.id)


    def save(self, commit=True):
        pm = super().save(commit=False)

        file_value, url_value = self.cleaned_data['photo']
        if file_value:
            pm.image = file_value
            pm.link = None
        elif url_value:
            pm.link = url_value
            pm.image = None
        else:
            return 
        
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


class BulkCollectibleForm(ModelForm):
    """Simplified form for bulk editing PlayerItems in a formset."""

    class Meta:
        model = PlayerItem
        fields = ['title', 'league', 'player', 'team', 'number', 'description']
        widgets = {
            'title': flowbite_widgets.FlowbiteTextInput(),
            'league': flowbite_widgets.FlowbiteTextInput(),
            'player': flowbite_widgets.FlowbiteTextInput(),
            'team': flowbite_widgets.FlowbiteTextInput(),
            'description': flowbite_widgets.FlowbiteTextarea(attrs={'rows': 1}),
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


class BulkPlayerGearItemForm(ModelForm):
    """Simplified form for bulk editing PlayerGearItems in a formset."""

    game_type = ModelChoiceField(queryset=GameType.objects.all(), widget=flowbite_widgets.FlowbiteSelectInput)
    usage_type = ModelChoiceField(queryset=UsageType.objects.all(), widget=flowbite_widgets.FlowbiteSelectInput)

    class Meta:
        model = PlayerGearItem
        fields = ['title', 'league', 'player', 'team', 'number', 'brand', 'size', 'season', 'game_type', 'usage_type', 'description']
        widgets = {
            'title': flowbite_widgets.FlowbiteTextInput(),
            'league': flowbite_widgets.FlowbiteTextInput(),
            'player': flowbite_widgets.FlowbiteTextInput(),
            'team': flowbite_widgets.FlowbiteTextInput(),
            'number': flowbite_widgets.FlowbiteNumberInput(),
            'brand': flowbite_widgets.FlowbiteTextInput(),
            'size': flowbite_widgets.FlowbiteTextInput(),
            'season': flowbite_widgets.FlowbiteTextInput(),
            'description': flowbite_widgets.FlowbiteTextarea(attrs={'rows': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['league'].widget.attrs.update({'placeholder': 'e.g., NHL, AHL...'})
        self.fields['team'].widget.attrs.update({'placeholder': 'Start typing a team...'})


class BulkOtherItemForm(ModelForm):
    """Simplified form for bulk editing OtherItems in a formset."""

    class Meta:
        model = OtherItem
        fields = ['title', 'description']
        widgets = {
            'title': flowbite_widgets.FlowbiteTextInput(),
            'description': flowbite_widgets.FlowbiteTextarea(attrs={'rows': 1}),
        }