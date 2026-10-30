from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Report
from .serializers import ReportSerializer

class ReportCreateView(generics.CreateAPIView):
    serializer_class = ReportSerializer
    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

class AdminReportListView(generics.ListAPIView):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Report.objects.select_related("reporter", "target_post", "target_comment", "target_user")

class AdminReportDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]
    def patch(self, request, pk):
        report = get_object_or_404(Report, pk=pk)
        next_status = request.data.get("status")
        if next_status not in {Report.REVIEWED, Report.DISMISSED, Report.OPEN}:
            return Response({"status": "Choose open, reviewed, or dismissed."}, status=400)
        report.status = next_status
        report.reviewed_at = timezone.now() if next_status != Report.OPEN else None
        report.save(update_fields=["status", "reviewed_at"])
        return Response(ReportSerializer(report).data)
    def delete(self, request, pk):
        report = get_object_or_404(Report, pk=pk)
        report.delete()
        return Response(status=204)
