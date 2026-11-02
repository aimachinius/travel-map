"""
Module batch_processor: Xử lý hàng loạt video từ file CSV, hỗ trợ checkpoint và tự phục hồi khi có lỗi.
"""

import os
import csv
import json
import time
from typing import Optional, List, Dict, Any

from ..config.settings import PipelineConfig, default_config
from ..pipeline.restaurant_pipeline import RestaurantExtractorPipeline, RestaurantExtractionResult
from ..utils.io_utils import read_csv_as_dicts, save_json_file
from ..utils.logger import get_logger

logger = get_logger("BatchProcessor")


class BatchProcessor:
    """
    Bộ xử lý hàng loạt video review ẩm thực từ file CSV kịch bản.
    """
    def __init__(
        self,
        pipeline: Optional[RestaurantExtractorPipeline] = None,
        config: Optional[PipelineConfig] = None,
    ):
        self.config = config or default_config
        self.pipeline = pipeline or RestaurantExtractorPipeline(config=self.config)

    def process_from_csv(
        self,
        csv_path: Optional[str] = None,
        videos_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        video_id_filter: Optional[str] = None,
        limit: Optional[int] = None,
        start_index: int = 0,
        start_video_id: Optional[str] = None,
        resume: bool = False,
        skip_existing: bool = True,
        save_interval: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Đọc danh sách video_id và text kịch bản từ CSV, chạy pipeline tự động cho từng video.
        Hỗ trợ:
        - start_index: Bắt đầu từ vị trí dòng chỉ định (0-based).
        - start_video_id: Bắt đầu từ video có ID cụ thể trong file CSV.
        - resume: Tự động tiếp tục từ video kế tiếp sau video đã hoàn thành gần nhất trong batch_results.csv.
        - Lưu định kỳ (checkpoint) sau mỗi N mẫu (mặc định: 10).
        - Bảo toàn toàn bộ kết quả đã chạy trước đó trong batch_results.csv khi ghi nối tiếp.
        """
        target_csv = csv_path or self.config.default_csv_path
        target_vids_dir = videos_dir or self.config.default_videos_dir
        target_out_dir = output_dir or self.config.default_output_dir
        interval = save_interval if save_interval is not None else getattr(self.config, "batch_save_interval", 10)

        os.makedirs(target_out_dir, exist_ok=True)
        csv_summary_path = os.path.join(target_out_dir, "batch_results.csv")
        summary_path = os.path.join(target_out_dir, "batch_summary.json")

        records = read_csv_as_dicts(target_csv)
        if not records:
            logger.warning(f"File CSV rỗng: {target_csv}")
            return {"total": 0, "processed": 0, "skipped": 0, "failed": 0, "results": []}

        total_in_csv = len(records)

        # 1. Nạp kết quả đã có sẵn từ batch_results.csv (nếu có) để bảo toàn và ghi nối tiếp
        existing_results_map: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(csv_summary_path) and skip_existing:
            try:
                existing_rows = read_csv_as_dicts(csv_summary_path)
                for r in existing_rows:
                    v_id = r.get("video_id")
                    if v_id:
                        existing_results_map[v_id] = r
                if existing_results_map:
                    logger.info(f"Đã nạp {len(existing_results_map)} kết quả sẵn có từ '{csv_summary_path}' để bảo toàn và ghi nối tiếp.")
            except Exception as e:
                logger.warning(f"Không thể đọc kết quả cũ từ CSV: {e}")

        # 2. Xử lý chế độ tự động RESUME
        if resume:
            if existing_results_map:
                last_processed_vid = list(existing_results_map.keys())[-1]
                found_idx = next((i for i, r in enumerate(records) if r.get("video_id") == last_processed_vid), None)
                if found_idx is not None:
                    start_index = found_idx + 1
                    logger.info(f"[RESUME] Video hoàn thành gần nhất: {last_processed_vid} (vị trí {found_idx}). Tự động tiếp tục từ index {start_index}/{total_in_csv}")
                else:
                    logger.warning(f"[RESUME] Video {last_processed_vid} không tìm thấy trong CSV! Tiếp tục theo start_index={start_index}")
            else:
                logger.info("[RESUME] Chưa có kết quả trước đó trong batch_results.csv, bắt đầu từ đầu.")

        # 3. Xử lý bắt đầu từ start_video_id
        elif start_video_id:
            target_vid_str = str(start_video_id).strip()
            found_idx = next((i for i, r in enumerate(records) if r.get("video_id") == target_vid_str), None)
            if found_idx is not None:
                start_index = found_idx
                logger.info(f"Đã định vị video_id '{target_vid_str}' tại vị trí dòng {start_index} trong CSV.")
            else:
                logger.warning(f"Không tìm thấy video_id '{target_vid_str}' trong file CSV! Sử dụng start_index={start_index}")

        # 4. Lọc theo video_id cụ thể (nếu có)
        if video_id_filter:
            records = [r for r in records if r.get("video_id") == str(video_id_filter)]
            start_index = 0

        # 5. Cắt danh sách từ vị trí bắt đầu
        actual_start_idx = max(0, start_index)
        if actual_start_idx > 0:
            if actual_start_idx >= len(records):
                logger.warning(f"Vị trí bắt đầu ({actual_start_idx}) >= tổng số dòng ({len(records)}). Không còn mẫu nào để xử lý.")
                return {"total": 0, "processed": 0, "skipped": 0, "failed": 0, "results": list(existing_results_map.values())}
            records = records[actual_start_idx:]

        # 6. Giới hạn số lượng limit
        if limit is not None and limit > 0:
            records = records[:limit]

        total = len(records)
        processed_count = 0
        skipped_count = 0
        failed_count = 0
        results: List[Dict[str, Any]] = []

        logger.info("=" * 65)
        logger.info("BẮT ĐẦU QUY TRÌNH XỬ LÝ HÀNG LOẠT (BATCH PROCESSING)")
        logger.info(f"File CSV:        {target_csv} (Tổng trong CSV: {total_in_csv} mẫu)")
        logger.info(f"Vị trí bắt đầu:  Dòng {actual_start_idx} (Số mẫu cần chạy lượt này: {total})")
        logger.info(f"Thư mục videos:  {target_vids_dir}")
        logger.info(f"Thư mục output:  {target_out_dir}")
        logger.info(f"Lưu định kỳ:     Mỗi {interval} mẫu")
        logger.info("=" * 65)

        batch_start_time = time.time()
        items_since_last_save = 0

        for idx, row in enumerate(records, 1):
            vid = row.get("video_id", "").strip()
            script_text = row.get("text", "").strip()
            csv_line_num = actual_start_idx + idx

            if not vid:
                continue

            video_file = os.path.join(target_vids_dir, f"{vid}.mp4")
            result_json_path = os.path.join(target_out_dir, vid, "result.json")

            # Kiểm tra bỏ qua nếu đã xử lý trước đó
            if skip_existing and os.path.exists(result_json_path):
                logger.info(f"[{idx}/{total}] (CSV #{csv_line_num}) [SKIP] Video {vid} đã có kết quả trước đó.")
                skipped_count += 1
                try:
                    with open(result_json_path, mode="r", encoding="utf-8") as f_json:
                        cached_res = json.load(f_json)
                    existing_results_map[vid] = cached_res
                    results.append(cached_res)
                except Exception as e:
                    logger.warning(f"Không thể nạp cache kết quả video {vid}: {e}")

                items_since_last_save += 1
                if interval > 0 and items_since_last_save >= interval:
                    self._save_checkpoint(
                        results=list(existing_results_map.values()) if existing_results_map else results,
                        csv_path=csv_summary_path,
                        summary_path=summary_path,
                        total=len(existing_results_map) if existing_results_map else total,
                        processed_count=processed_count,
                        skipped_count=skipped_count,
                        failed_count=failed_count,
                        start_time=batch_start_time,
                        target_out_dir=target_out_dir,
                    )
                    items_since_last_save = 0
                continue

            if not os.path.exists(video_file):
                logger.warning(f"[{idx}/{total}] (CSV #{csv_line_num}) [NOT FOUND] Không tìm thấy video: {video_file}")
                failed_count += 1
                fail_res = {
                    "video_id": vid,
                    "restaurant_name": None,
                    "address": None,
                    "nguồn_tên_quán": None,
                    "nguồn_địa_chỉ": None,
                    "log_detect": None,
                    "status": "NOT_FOUND",
                    "selected_frames_count": 0,
                    "frames_dir": None,
                    "execution_time_sec": 0.0,
                    "error_message": f"Không tìm thấy video: {video_file}",
                }
                existing_results_map[vid] = fail_res
                results.append(fail_res)
                items_since_last_save += 1
                if interval > 0 and items_since_last_save >= interval:
                    self._save_checkpoint(
                        results=list(existing_results_map.values()) if existing_results_map else results,
                        csv_path=csv_summary_path,
                        summary_path=summary_path,
                        total=len(existing_results_map) if existing_results_map else total,
                        processed_count=processed_count,
                        skipped_count=skipped_count,
                        failed_count=failed_count,
                        start_time=batch_start_time,
                        target_out_dir=target_out_dir,
                    )
                    items_since_last_save = 0
                continue

            logger.info(f"[{idx}/{total}] (CSV #{csv_line_num}) Đang xử lý video {vid}...")
            try:
                res: RestaurantExtractionResult = self.pipeline.process_video(
                    video_path=video_file,
                    script=script_text,
                    video_id=vid,
                )
                res_dict = res.to_dict()
                existing_results_map[vid] = res_dict
                results.append(res_dict)

                # Lưu kết quả riêng lẻ của từng video
                save_json_file(res_dict, result_json_path)

                if res.status == "SUCCESS":
                    processed_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"[{idx}/{total}] Lỗi không mong muốn khi xử lý video {vid}: {e}")
                failed_count += 1
                fail_res = {
                    "video_id": vid,
                    "restaurant_name": None,
                    "address": None,
                    "nguồn_tên_quán": None,
                    "nguồn_địa_chỉ": None,
                    "log_detect": None,
                    "status": "FAILED",
                    "selected_frames_count": 0,
                    "frames_dir": None,
                    "execution_time_sec": 0.0,
                    "error_message": str(e),
                }
                existing_results_map[vid] = fail_res
                results.append(fail_res)

            items_since_last_save += 1
            if interval > 0 and items_since_last_save >= interval:
                self._save_checkpoint(
                    results=list(existing_results_map.values()) if existing_results_map else results,
                    csv_path=csv_summary_path,
                    summary_path=summary_path,
                    total=len(existing_results_map) if existing_results_map else total,
                    processed_count=processed_count,
                    skipped_count=skipped_count,
                    failed_count=failed_count,
                    start_time=batch_start_time,
                    target_out_dir=target_out_dir,
                )
                items_since_last_save = 0

        total_elapsed = time.time() - batch_start_time
        all_results_to_export = list(existing_results_map.values()) if existing_results_map else results

        # Lưu kết quả tổng hợp ra CSV & JSON (lần cuối)
        summary_data = {
            "total_items": len(all_results_to_export),
            "batch_run_items": total,
            "processed_success": processed_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "start_index": actual_start_idx,
            "total_time_seconds": round(total_elapsed, 2),
            "output_directory": target_out_dir,
        }
        save_json_file(summary_data, summary_path)
        self._export_results_to_csv(all_results_to_export, csv_summary_path)

        logger.info("=" * 65)
        logger.info(f"HOÀN THÀNH: Đợt này {processed_count}/{total} thành công | Bỏ qua {skipped_count} | Thất bại {failed_count}")
        logger.info(f"Tổng kết quả tích lũy trong CSV: {len(all_results_to_export)} mẫu")
        logger.info(f"Tổng thời gian: {total_elapsed:.2f}s | Báo cáo: {summary_path}")
        logger.info(f"Kết quả CSV:    {csv_summary_path}")
        logger.info("=" * 65)

        return {
            "summary": summary_data,
            "results": all_results_to_export,
        }

    def _save_checkpoint(
        self,
        results: List[Dict[str, Any]],
        csv_path: str,
        summary_path: str,
        total: int,
        processed_count: int,
        skipped_count: int,
        failed_count: int,
        start_time: float,
        target_out_dir: str,
    ):
        """
        Lưu định kỳ kết quả hiện tại ra CSV và file tóm tắt JSON.
        """
        elapsed = time.time() - start_time
        summary_data = {
            "total_items": total,
            "processed_success": processed_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "total_time_seconds": round(elapsed, 2),
            "output_directory": target_out_dir,
            "checkpoint_at": len(results),
        }
        save_json_file(summary_data, summary_path)
        self._export_results_to_csv(results, csv_path)
        logger.info(
            f"[CHECKPOINT] Đã lưu định kỳ {len(results)} mẫu vào '{csv_path}' "
            f"(Thành công: {processed_count}, Bỏ qua: {skipped_count}, Thất bại: {failed_count})"
        )

    def _export_results_to_csv(self, results: List[Dict[str, Any]], csv_path: str):
        if not results:
            return
        fieldnames = [
            "video_id",
            "restaurant_name",
            "address",
            "nguồn_tên_quán",
            "nguồn_địa_chỉ",
            "log_detect",
            "status",
            "selected_frames_count",
            "frames_dir",
            "execution_time_sec",
            "error_message",
        ]
        try:
            with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for r in results:
                    # Tự động trích xuất nguồn nếu dữ liệu từ cache cũ chưa có sẵn ở root
                    if not r.get("nguồn_tên_quán") or not r.get("nguồn_địa_chỉ"):
                        evidence = r.get("evidence")
                        if isinstance(evidence, dict):
                            r["nguồn_tên_quán"] = r.get("nguồn_tên_quán") or evidence.get("nguồn_tên_quán")
                            r["nguồn_địa_chỉ"] = r.get("nguồn_địa_chỉ") or evidence.get("nguồn_địa_chỉ")
                        raw_out = r.get("raw_vlm_output")
                        if raw_out and (not r.get("nguồn_tên_quán") or not r.get("nguồn_địa_chỉ")):
                            try:
                                parsed = json.loads(raw_out) if isinstance(raw_out, str) else raw_out
                                dan_chung = parsed.get("dẫn_chứng", {})
                                r["nguồn_tên_quán"] = r.get("nguồn_tên_quán") or dan_chung.get("nguồn_tên_quán")
                                r["nguồn_địa_chỉ"] = r.get("nguồn_địa_chỉ") or dan_chung.get("nguồn_địa_chỉ")
                            except Exception:
                                pass

                    # Tự động trích xuất log_detect nếu dữ liệu từ cache cũ chưa có sẵn ở root
                    if not r.get("log_detect"):
                        raw_out = r.get("raw_vlm_output")
                        if raw_out:
                            try:
                                parsed = json.loads(raw_out) if isinstance(raw_out, str) else raw_out
                                if parsed.get("log_detect"):
                                    r["log_detect"] = parsed.get("log_detect")
                                elif parsed.get("chi_tiết_frames"):
                                    frames = parsed.get("chi_tiết_frames", [])
                                    tot = len(frames)
                                    r["log_detect"] = "\n".join([
                                        f.get("log_line") or f"[Frame {f.get('frame_idx', i)}/{tot}] -> Tên OCR: {f.get('tên_quán_ocr')} | Địa chỉ OCR: {f.get('địa_chỉ_ocr')} | Chữ khác: {f.get('chữ_khác_ocr')}"
                                        for i, f in enumerate(frames, 1)
                                    ])
                            except Exception:
                                pass
                        if not r.get("log_detect") and r.get("chi_tiết_frames"):
                            frames = r.get("chi_tiết_frames", [])
                            tot = len(frames)
                            r["log_detect"] = "\n".join([
                                f.get("log_line") or f"[Frame {f.get('frame_idx', i)}/{tot}] -> Tên OCR: {f.get('tên_quán_ocr')} | Địa chỉ OCR: {f.get('địa_chỉ_ocr')} | Chữ khác: {f.get('chữ_khác_ocr')}"
                                for i, f in enumerate(frames, 1)
                            ])

                    writer.writerow(r)
        except Exception as e:
            logger.warning(f"Không thể ghi kết quả ra CSV {csv_path}: {e}")
