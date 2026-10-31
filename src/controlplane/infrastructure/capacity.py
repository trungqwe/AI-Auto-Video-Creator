"""Trần tài nguyên cho tối đa 10 luồng video chạy cùng lúc (ADAPT-PROD-FIX4, quyết định user 31/10/2026)."""
from types import MappingProxyType

MAX_VIDEO_STREAMS = 10
# 36 kết nối: hai cho mỗi luồng gọi AI (giữ kết nối suốt lời gọi 9Router và mượn thêm một kết nối cho ledger/reservation), 8 cho API/SSE, 8 cho thu thập/enrichment.
DB_POOL_MAX_SIZE = 2 * MAX_VIDEO_STREAMS + 16
# Trần activity đồng thời theo task queue; queue không có trong bảng này giữ mặc định của SDK.
ACTIVITY_QUEUE_CAPS = MappingProxyType({'cloud-io': 16, 'cloud-ai': 8})
# 48 luồng: 10 video, 16 cloud-io, 8 cloud-ai, 8 control, 3 nền, 3 dư.
ACTIVITY_THREADS = MAX_VIDEO_STREAMS + 38
