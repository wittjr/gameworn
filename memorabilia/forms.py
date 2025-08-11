from django import forms
from django.forms import BaseInlineFormSet, ModelForm, CheckboxInput, ImageField, ModelChoiceField, ClearableFileInput, FileField, FilePathField, MultiValueField, inlineformset_factory

from django_flowbite_widgets.flowbite_fields import FlowbiteImageDropzoneField
from .models import Collectible, Collection, PhotoMatch, League, GameType, UsageType, CollectibleImage
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
        help_text="Upload a file or enter an image URL",
        # required=False,
        # max_file_size=5*1024*1024,  # 2MB
        # allowed_extensions=['jpg', 'jpeg', 'png']
        file_field_name='image',
        url_field_name='image_link'
    )

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


    def save(self, commit=True):
        instance = super().save(commit=False)

        file_value, url_value = self.cleaned_data['header_image']
        if file_value:
            instance.image = file_value
            instance.image_link = None
        elif url_value:
            instance.image_link = url_value
            instance.image = None
        else:
            return 
        
        if commit:
            instance.save()
        
        return instance


class CollectibleForm(ModelForm):
    league = ModelChoiceField(
        queryset=League.objects.all(),
        widget=flowbite_widgets.FlowbiteSelectInput,
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
        model = Collectible
        fields = "__all__"
        exclude = ['for_sale', 'for_trade', 'looking_for', 'asking_price', 'images']
        widgets = {
            "title": flowbite_widgets.FlowbiteTextInput(),
            "brand": flowbite_widgets.FlowbiteTextInput(),
            "size": flowbite_widgets.FlowbiteTextInput(),
            "player": flowbite_widgets.FlowbiteTextInput(),
            "season": flowbite_widgets.FlowbiteTextInput(),
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
        

    def get_image_fields(self):
        for field_name in self.fields:
            if field_name.startswith("image_"):
                yield self[field_name]

    def clean_league(self):
        data = self.cleaned_data["league"].pk
        return data

    def clean_game_type(self):
        data = self.cleaned_data["game_type"].pk
        return data

    def clean_usage_type(self):
        data = self.cleaned_data["usage_type"].pk
        return data


class CollectibleImageForm(ModelForm):

    # images = ImageGallery(required=False)

    class Meta:
        model = CollectibleImage
        fields = "__all__"
        widgets = {
            # "image": flowbite_widgets.FlowbiteTextInput(),
            "link": flowbite_widgets.FlowbiteTextInput(),
            "primary": flowbite_widgets.FlowbiteCheckboxInput(),
            "flickrObject": flowbite_widgets.FlowbiteTextarea(),
        }


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
    Collectible, 
    CollectibleImage, 
    form=CollectibleImageForm,
    formset=CustomCollectibleImageFormSet,
    extra=0,
    can_delete=True,
    # min_num=0,
    # validate_min=True,
    # max_num=10,
    # validate_max=True
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
        