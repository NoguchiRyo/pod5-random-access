#include "pod5_signal_index.hpp"
#include "pod5_format/c_api.h"

#include <algorithm>
#include <cstring>
#include <fstream>
#include <numeric>
#include <stdexcept>
#include <vector>

namespace pod5 {

static_assert(sizeof(SigLoc) == 24, "SigLoc must be 24 bytes");

// --------------------------------------------------------------------------
//  インデックス構築
// --------------------------------------------------------------------------
SignalIndex build_signal_index(Pod5FileReader_t *reader) {
  SignalIndex idx;

  // (A) Read Table バッチ数を取得
  size_t batch_count = 0;
  if (pod5_get_read_batch_count(&batch_count, reader) != POD5_OK) {
    throw std::runtime_error("pod5_get_read_batch_count failed");
  }

  // (B) 各バッチを順に走査
  for (size_t b = 0; b < batch_count; ++b) {
    Pod5ReadRecordBatch_t *batch = nullptr;
    if (pod5_get_read_batch(&batch, reader, b) != POD5_OK) {
      throw std::runtime_error("pod5_get_read_batch failed");
    }

    size_t row_count = 0;
    if (pod5_get_read_batch_row_count(&row_count, batch) != POD5_OK) {
      pod5_free_read_batch(batch);
      throw std::runtime_error("pod5_get_read_batch_row_count failed");
    }

    for (size_t r = 0; r < row_count; ++r) {
      // (1) 行情報を取得（UUID, calibration, signal_row_count, num_samples）
      ReadBatchRowInfo_t info{};
      uint16_t table_ver = 0;
      if (pod5_get_read_batch_row_info_data(batch, r,
                                            READ_BATCH_ROW_INFO_VERSION, &info,
                                            &table_ver) != POD5_OK) {
        pod5_free_read_batch(batch);
        throw std::runtime_error("pod5_get_read_batch_row_info_data failed");
      }

      // (2) signal row indices を取得（連続であることが保証されている）
      std::vector<uint64_t> signal_rows(info.signal_row_count);
      if (pod5_get_signal_row_indices(batch, r, info.signal_row_count,
                                      signal_rows.data()) != POD5_OK) {
        pod5_free_read_batch(batch);
        throw std::runtime_error("pod5_get_signal_row_indices failed");
      }

      // (3) UUID → SigLoc を登録
      ReadId id;
      std::memcpy(id.data(), info.read_id, 16);

      SigLoc loc{
          signal_rows[0],
          static_cast<uint32_t>(info.signal_row_count),
          static_cast<uint32_t>(info.num_samples),
          info.calibration_offset,
          info.calibration_scale,
      };

      idx.emplace(id, loc);
    }

    if (pod5_free_read_batch(batch) != POD5_OK) {
      throw std::runtime_error("pod5_free_read_batch failed");
    }
  }

  return idx;
}

// --------------------------------------------------------------------------
//  バイナリシリアライズ
// --------------------------------------------------------------------------
static constexpr char MAGIC[6] = "P5IDX";
static constexpr uint16_t VERSION = 1;

struct FileHeader {
  char magic[6];
  uint16_t ver;
  uint16_t reserved{};
  uint64_t entry_count{};
};

void save_index_bin(const SignalIndex &idx, const std::string &path) {
  std::ofstream ofs(path, std::ios::out | std::ios::trunc | std::ios::binary);
  if (!ofs)
    throw std::runtime_error("open failed");

  FileHeader hdr{};
  std::memcpy(hdr.magic, MAGIC, 6);
  hdr.ver = VERSION;
  hdr.entry_count = idx.size();
  ofs.write(reinterpret_cast<char *>(&hdr), sizeof hdr);

  for (auto const &[key, loc] : idx) {
    ofs.write(reinterpret_cast<char const *>(key.data()), key.size());
    ofs.write(reinterpret_cast<char const *>(&loc), sizeof loc);
  }
}

SignalIndex load_index_bin(const std::string &path) {
  std::ifstream ifs(path, std::ios::binary);
  if (!ifs)
    throw std::runtime_error("open failed");

  FileHeader hdr{};
  ifs.read(reinterpret_cast<char *>(&hdr), sizeof hdr);
  if (std::memcmp(hdr.magic, MAGIC, 6) || hdr.ver != VERSION)
    throw std::runtime_error("format mismatch");

  SignalIndex idx;
  idx.reserve(static_cast<size_t>(hdr.entry_count * 1.3));

  for (uint64_t i = 0; i < hdr.entry_count; ++i) {
    ReadId key{};
    ifs.read(reinterpret_cast<char *>(key.data()), key.size());

    SigLoc loc{};
    ifs.read(reinterpret_cast<char *>(&loc), sizeof loc);

    idx.emplace(std::move(key), loc);
  }
  return idx;
}

// --------------------------------------------------------------------------
//  シグナル読み込み（Signal Table 直接アクセス）
// --------------------------------------------------------------------------
std::vector<int16_t> fetch_signal(Pod5FileReader_t *reader,
                                  SigLoc const &loc) {
  // (1) 連続する signal row indices を再構成
  std::vector<uint64_t> signal_rows(loc.signal_row_count);
  for (uint32_t i = 0; i < loc.signal_row_count; ++i) {
    signal_rows[i] = loc.signal_row_start + i;
  }

  // (2) Signal Table から row 情報を取得
  std::vector<SignalRowInfo_t *> row_infos(loc.signal_row_count);
  if (pod5_get_signal_row_info(reader, loc.signal_row_count,
                                signal_rows.data(),
                                row_infos.data()) != POD5_OK) {
    throw std::runtime_error("pod5_get_signal_row_info failed");
  }

  // (3) 各 signal row からサンプルを読み込み
  std::vector<int16_t> signal(loc.n_samples);
  size_t offset = 0;
  for (uint32_t i = 0; i < loc.signal_row_count; ++i) {
    size_t chunk_samples = row_infos[i]->stored_sample_count;
    if (pod5_get_signal(reader, row_infos[i], chunk_samples,
                        signal.data() + offset) != POD5_OK) {
      pod5_free_signal_row_info(loc.signal_row_count, row_infos.data());
      throw std::runtime_error("pod5_get_signal failed");
    }
    offset += chunk_samples;
  }

  // (4) row info を解放
  pod5_free_signal_row_info(loc.signal_row_count, row_infos.data());

  return signal;
}

// --------------------------------------------------------------------------
//  pA キャリブレーション済みシグナル読み込み
// --------------------------------------------------------------------------
std::vector<float> fetch_pA_signal(Pod5FileReader_t *reader,
                                   SigLoc const &loc) {
  auto raw = fetch_signal(reader, loc);

  std::vector<float> pA(raw.size());
  const float offset = loc.calibration_offset;
  const float scale = loc.calibration_scale;
  for (size_t i = 0; i < raw.size(); ++i) {
    pA[i] = (static_cast<float>(raw[i]) + offset) * scale;
  }

  return pA;
}

// --------------------------------------------------------------------------
//  ソート
// --------------------------------------------------------------------------
std::vector<size_t> sort_by_location(SignalIndex const &index,
                                     std::vector<ReadId> const &ids) {
  std::vector<size_t> order(ids.size());
  std::iota(order.begin(), order.end(), 0);

  // signal_row_start の昇順 = Signal Table 上の物理順
  std::sort(order.begin(), order.end(), [&](size_t a, size_t b) {
    auto it_a = index.find(ids[a]);
    auto it_b = index.find(ids[b]);
    if (it_a == index.end() || it_b == index.end())
      throw std::out_of_range("UUID not found in SignalIndex");
    return it_a->second.signal_row_start < it_b->second.signal_row_start;
  });

  return order;
}

} // namespace pod5
