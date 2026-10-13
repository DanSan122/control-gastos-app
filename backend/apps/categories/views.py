from apps.core.finance import OwnedViewSet
from .models import Area, Category, Subcategory
from .serializers import AreaSerializer, CategorySerializer, SubcategorySerializer


class AreaViewSet(OwnedViewSet):
    queryset = Area.objects.all()
    serializer_class = AreaSerializer


class CategoryViewSet(OwnedViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    relation_filters = ["area"]


class SubcategoryViewSet(OwnedViewSet):
    queryset = Subcategory.objects.all()
    serializer_class = SubcategorySerializer
    relation_filters = ["category"]
