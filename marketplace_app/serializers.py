from rest_framework import serializers
from .models import User, Category, Listing, ListingImage, StoreProfile, CommonProfile

# --- Tradutores de Anúncios (Para a Vitrine do React) ---

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ['id', 'image']

class ListingSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    seller_name = serializers.ReadOnlyField(source='seller.username')

    class Meta:
        model = Listing
        fields = [
            'id', 'seller', 'seller_name', 'category', 'title', 
            'description', 'price', 'listing_type', 'condition', 
            'status', 'is_featured', 'is_store_featured', 
            'created_at', 'images'
        ]

# --- Tradutor de Registro (Para o seu Front de Cadastro) ---

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    is_store = serializers.BooleanField(default=False)
    cpf = serializers.CharField(required=False, allow_blank=True)
    cnpj = serializers.CharField(required=False, allow_blank=True)
    razao_social = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'is_store', 'cpf', 'cnpj', 'razao_social']

    def create(self, validated_data):
        cpf = validated_data.pop('cpf', None)
        cnpj = validated_data.pop('cnpj', None)
        razao_social = validated_data.pop('razao_social', None)
        is_store = validated_data.get('is_store', False)

        user = User.objects.create_user(**validated_data)

        if is_store:
            StoreProfile.objects.create(user=user, cnpj=cnpj, razao_social=razao_social)
        else:
            CommonProfile.objects.create(user=user, cpf=cpf)
        return user