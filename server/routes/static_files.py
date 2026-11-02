"""
Module static_files: Phục vụ xem/tải các tệp video MP4 và ảnh keyframes trực tiếp trên server.
"""

import os
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import FileResponse

from ..dependencies import get_server_config

router = APIRouter(prefix="/api/v1", tags=["Static Media"])


@router.get(
    "/videos/{filename}",
    summary="Xem trực tiếp hoặc tải file video MP4 đã lưu trữ",
)
async def get_video_file(filename: str, config = Depends(get_server_config)):
    clean_filename = os.path.basename(filename)
    file_path = os.path.join(config.videos_dir, clean_filename)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy file video: '{clean_filename}'. Có thể file đã bị xóa do chính sách dọn dẹp bộ nhớ."
        )

    return FileResponse(file_path, media_type="video/mp4", filename=clean_filename)


@router.get(
    "/keyframes/{video_id}/{filename}",
    summary="Xem ảnh keyframe trích chọn có vẽ bounding box biển hiệu",
)
async def get_keyframe_image(video_id: str, filename: str, config = Depends(get_server_config)):
    clean_vid = os.path.basename(video_id)
    clean_fname = os.path.basename(filename)

    file_path = os.path.join(
        config.keyframes_dir, clean_vid, "selected_text_frames_drawn", clean_fname
    )

    # Nếu không thấy trong thư mục con drawn, thử tìm trực tiếp trong thư mục video_id
    if not os.path.exists(file_path):
        alt_path = os.path.join(config.keyframes_dir, clean_vid, clean_fname)
        if os.path.exists(alt_path):
            file_path = alt_path
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy ảnh keyframe: '{clean_fname}'"
            )

    return FileResponse(file_path, media_type="image/jpeg", filename=clean_fname)
