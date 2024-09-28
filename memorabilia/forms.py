from django.forms import ModelForm, CheckboxInput, ImageField, ModelChoiceField, ClearableFileInput, FileField
from .models import Collectible, Collection, PhotoMatch, League, GameType, UsageType, CollectibleImage
from django.conf import settings
from django.core.files import File
from django.core.files.uploadedfile import InMemoryUploadedFile
import os
from django.core.files.storage import default_storage

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
    class Meta:
        model = Collection
        fields = [
            'owner_uid',
            'title',
            'image',
            'image_link'
        ]


    # def clean(self):
        # self.cleaned_data = super().clean()
        # if self.cleaned_data['image']:
        #     self.cleaned_data['image_link'] = settings.MEDIA_URL + self.cleaned_data['image'].name


    # def save(self):
    #     collection = self.instance
    #     # print(vars(self))
    #     # print(collection.image)
    #     # print(vars(collection))
    #     # print(self.instance)
    #     # print(vars(self.instance))
    #     # print(self.changed_data)
    #     # print(self.cleaned_data)
    #     if self.cleaned_data['image']:
    #         self.instance.image_link = settings.MEDIA_URL + self.cleaned_data['image'].name
    #     # current_images = set()
    #     # for o in self.cleaned_data['images']:
    #     #     if type(o) == File:
    #     #         current_images.add(o.name)
    #     # for image in list(collection.images.values()):
    #     #     file_path = os.path.join(settings.MEDIA_URL, image['image'])
    #     #     if file_path not in current_images:
    #     #         default_storage.delete(image['image'])
    #     #         CollectibleImage.objects.get(image = image['image']).delete()

    #     # for image in self.cleaned_data['images']:
    #     #     # print(image)
    #     #     if isinstance(image, InMemoryUploadedFile):
    #     #         CollectibleImage.objects.create(
    #     #             collectible=collectible,
    #     #             image=image,
    #     #         )
    #     self.instance.save()


class CollectibleForm(ModelForm):
    league = ModelChoiceField(queryset=League.objects.all())
    game_type = ModelChoiceField(queryset=GameType.objects.all())
    usage_type = ModelChoiceField(queryset=UsageType.objects.all())

    # images = MultipleFileField()

    class Meta:
        model = Collectible
        fields = '__all__'
        # fields = [
            # 'title',
            # 'description',
            # 'season',
            # 'league',
            # 'brand',
            # 'size',
            # 'player',
            # 'description',
            # 'usage_type',
            # 'game_type',
            # 'collection',
            # 'for_sale',
            # 'for_trade',
            # 'asking_price',
            # 'looking_for',
            # 'images'
        # ]
        # exclude = ['images']
        widgets = {
            'for_sale': CheckboxInput(),
            'for_trade': CheckboxInput()
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        collectible=self.instance
        image_count=0
        if (collectible.id != None):
            images = collectible.images.values()
            # images = Collectible.objects.filter(pk=collectible.id)
            image_count = images.count()
            i=0
            for image in images:
                field_name = 'image_%s' % (i,)
                self.fields[field_name] = ImageField(required=False)
                try:
                    file_path = os.path.join(settings.MEDIA_ROOT, image['image'])
                    self.fields[field_name].initial = File(open(file_path))
                    self.fields[field_name].initial.name = default_storage.url(image['image'])
                    self.fields[field_name].initial.url = default_storage.url(image['image'])
                except (IndexError, FileNotFoundError):
                    self.initial[field_name] = ''
                i += 1
        # create an extra blank field
        field_name = 'image_%s' % (image_count,)
        self.fields[field_name] = ImageField(required=False)

    def clean(self):
        self.cleaned_data = super().clean()
        images = set()
        i = 0
        field_name = 'image_%s' % (i)
        while field_name in self.cleaned_data:
            image = self.cleaned_data[field_name]
            if image:
                if image in images:
                    self.add_error(field_name, 'Duplicate')
                else:
                    images.add(image)
            i += 1
            field_name = 'image_%s' % (i,)
        self.cleaned_data['images'] = images

    def save(self):
        collectible = self.instance
        current_images = set()
        for o in self.cleaned_data['images']:
            if type(o) == File:
                current_images.add(o.name)
        for image in list(collectible.images.values()):
            file_path = os.path.join(settings.MEDIA_URL, image['image'])
            if file_path not in current_images:
                default_storage.delete(image['image'])
                CollectibleImage.objects.get(image = image['image']).delete()

        for image in self.cleaned_data['images']:
            # print(image)
            if isinstance(image, InMemoryUploadedFile):
                CollectibleImage.objects.create(
                    collectible=collectible,
                    image=image,
                )
        self.instance.save()

    def get_image_fields(self):
        for field_name in self.fields:
            if field_name.startswith('image_'):
                yield self[field_name]

    def clean_league(self):
        data = self.cleaned_data['league'].pk
        return data

    def clean_game_type(self):
        data = self.cleaned_data['game_type'].pk
        return data

    def clean_usage_type(self):
        data = self.cleaned_data['usage_type'].pk
        return data

class CollectibleImageForm(ModelForm):
    class Meta:
        model = CollectibleImage
        fields = fields = '__all__'


class PhotoMatchForm(ModelForm):
    class Meta:
        model = PhotoMatch
        fields = [
            'collectible',
            'game_date',
            'image'
        ]