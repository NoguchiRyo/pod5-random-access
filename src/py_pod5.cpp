#include "pod5_format/c_api.h"
#include "pod5_signal_index.hpp" // ← 先に作った C++ ヘッダ群

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/pytypes.h>
#include <pybind11/stl.h> // std::vector などを自動変換

namespace py = pybind11;
using ReadId = pod5::ReadId;
using SigLoc = pod5::SigLoc;
using SignalIndex = pod5::SignalIndex;

/* ========================================================================== */
/*  内部ユーティリティ                                                        */
/* ========================================================================== */

// Python 引数 (bytes/str) → 16-byte ReadId 変換
static ReadId to_read_id(py::object obj) {
  ReadId id{};

  if (py::isinstance<py::bytes>(obj)) {
    std::string b = obj.cast<std::string>();
    if (b.size() != 16)
      throw std::invalid_argument("UUID bytes must be length-16");
    std::memcpy(id.data(), b.data(), 16);
  } else if (py::isinstance<py::str>(obj)) {
    std::string s = obj.cast<std::string>(); // "8-4-4-4-12" or 32hex
    std::string hex;
    for (char c : s)
      if (c != '-')
        hex += c;
    if (hex.size() != 32)
      throw std::invalid_argument("UUID string must be 32 hex digits");
    for (size_t i = 0; i < 16; ++i) {
      unsigned int v;
      sscanf(hex.substr(i * 2, 2).c_str(), "%02x", &v);
      id[i] = static_cast<uint8_t>(v);
    }
  } else {
    throw std::invalid_argument("UUID must be bytes or str");
  }
  return id;
}

// vector<int16_t> → numpy.ndarray<int16>
static py::array_t<int16_t> to_numpy(std::vector<int16_t> const &v) {
  auto arr = py::array_t<int16_t>(v.size());
  std::memcpy(arr.mutable_data(), v.data(), v.size() * sizeof(int16_t));
  return arr;
}

/* ========================================================================== */
/*  ラッパークラス */
/* ========================================================================== */
class PyPod5Index {
public:
  explicit PyPod5Index(const std::string &file) {
    if (pod5_init() != POD5_OK)
      throw std::runtime_error("pod5_init failed");
    reader_ = pod5_open_file(file.c_str());
    if (!reader_)
      throw std::runtime_error("pod5_open_file failed");
  }

  ~PyPod5Index() {
    for (auto &p : batch_cache_)
      pod5_free_read_batch(p.second);
    if (reader_)
      pod5_close_and_free_reader(reader_);
    pod5_terminate();
  }

  void build_index() { idx_ = pod5::build_signal_index(reader_); }
  void save_index(const std::string &path) const {
    pod5::save_index_bin(idx_, path);
  }
  void load_index(const std::string &path) {
    idx_ = pod5::load_index_bin(path);
  }

  float_t get_calibration_offset(py::object uuid) const {
    ReadId id = to_read_id(uuid);
    auto it = idx_.find(id);
    if (it == idx_.end())
      throw std::out_of_range("UUID not in index");
    const SigLoc &loc = it->second.front();
    return loc.calibration_offset;
  }

  float_t get_calibration_scale(py::object uuid) const {
    ReadId id = to_read_id(uuid);
    auto it = idx_.find(id);
    if (it == idx_.end())
      throw std::out_of_range("UUID not in index");
    const SigLoc &loc = it->second.front();
    return loc.calibration_scale;
  }

  py::tuple get_calibration(py::object uuid) const {
    ReadId id = to_read_id(uuid);
    auto it = idx_.find(id);
    if (it == idx_.end())
      throw std::out_of_range("UUID not in index");
    const SigLoc &loc = it->second.front();
    // return a 2-tuple (offset, scale)
    return py::make_tuple(loc.calibration_offset, loc.calibration_scale);
  }

  /** シングル UUID → numpy array (vector 省略、直接 numpy に読み込む) */
  py::array_t<int16_t> fetch_signal(py::object uuid) const {
    // --- GIL 必要部分: Pythonオブジェクト操作 ---
    ReadId id = to_read_id(uuid);
    auto it = idx_.find(id);
    if (it == idx_.end())
      throw std::out_of_range("UUID not in index");
    const SigLoc &loc = it->second.front();
    Pod5ReadRecordBatch_t *batch = get_or_load_batch(loc.batch);
    size_t n = loc.n_samples;

    std::vector<int16_t> buf(n); // 一時バッファ

    // --- I/O & デコード部分だけ GIL 解放 ---
    {
      py::gil_scoped_release release;
      if (pod5_get_read_complete_signal(reader_, batch, loc.row, n,
                                        buf.data()) != POD5_OK)
        throw std::runtime_error("pod5_get_read_complete_signal failed");
    }

    // --- GIL 再取得後に Python API 呼び出し ---
    auto arr = py::array_t<int16_t>(n);
    std::memcpy(arr.mutable_data(), buf.data(), n * sizeof(int16_t));
    return arr;
  }

  /** 複数 UUID list → Python list of numpy arrays (並列実行 + IO中に numpy
   * copy) */
  // Parallel fetch: IO overlapped with numpy copy
  py::list fetch_signals(py::iterable const &uuid_list) const {
    // (1) UUID→ReadId vector
    std::vector<ReadId> ids;
    for (auto h : uuid_list) {
      ids.push_back(to_read_id(h.cast<py::object>()));
    }
    // (2) batch 単位で読み込み
    std::vector<std::vector<int16_t>> raw_signals;
    {
      py::gil_scoped_release release;
      raw_signals =
          pod5::fetch_signals_by_batch(reader_, idx_, ids, batch_cache_);
    }
    // (3) Python 配列へ変換
    py::list out;
    for (auto &vec : raw_signals) {
      auto arr = py::array_t<int16_t>(vec.size());
      std::memcpy(arr.mutable_data(), vec.data(), vec.size() * sizeof(int16_t));
      out.append(arr);
    }
    return out;
  }

  /** 全ての read_id を文字列化して返す */
  std::vector<std::string> list_read_ids() const {
    std::vector<std::string> out;
    out.reserve(idx_.size());
    char buf[37]; // 36-char UUID + NUL

    for (auto const &p : idx_) {
      // p.first は ReadId = std::array<uint8_t,16>
      pod5_format_read_id(p.first.data(), buf);
      out.emplace_back(buf);
    }
    return out;
  }

  /** Get signal length for a given UUID without fetching the actual signal */
  size_t get_signal_length(py::object uuid) const {
    ReadId id = to_read_id(uuid);
    auto it = idx_.find(id);
    if (it == idx_.end())
      throw std::out_of_range("UUID not in index");
    const SigLoc &loc = it->second.front();
    return loc.n_samples;
  }

private:
  Pod5FileReader_t *reader_{nullptr};
  SignalIndex idx_;
  mutable std::unordered_map<uint32_t, Pod5ReadRecordBatch_t *> batch_cache_;

  Pod5ReadRecordBatch_t *get_or_load_batch(uint32_t bid) const {
    auto it = batch_cache_.find(bid);
    if (it != batch_cache_.end())
      return it->second;
    Pod5ReadRecordBatch_t *batch = nullptr;
    if (pod5_get_read_batch(&batch, reader_, bid) != POD5_OK)
      throw std::runtime_error("pod5_get_read_batch failed");
    batch_cache_[bid] = batch;
    return batch;
  }

  static ReadId to_read_id(py::object obj) {
    ReadId id{};
    if (py::isinstance<py::bytes>(obj)) {
      auto b = obj.cast<std::string>();
      if (b.size() != 16)
        throw std::invalid_argument("UUID bytes must be length-16");
      std::memcpy(id.data(), b.data(), 16);
    } else if (py::isinstance<py::str>(obj)) {
      std::string s = obj.cast<std::string>(), hex;
      for (char c : s)
        if (c != '-')
          hex += c;
      if (hex.size() != 32)
        throw std::invalid_argument("UUID string must be 32 hex digits");
      for (size_t i = 0; i < 16; ++i) {
        unsigned v;
        sscanf(hex.substr(i * 2, 2).c_str(), "%02x", &v);
        id[i] = static_cast<uint8_t>(v);
      }
    } else
      throw std::invalid_argument("UUID must be bytes or str");
    return id;
  }
};

/* ========================================================================== */
/*  pybind11 モジュール定義                                                   */
/* ========================================================================== */
PYBIND11_MODULE(pod5_random_access_pybind, m) {
  m.doc() = "Minimal POD5 signal-index wrapper";

  /* SigLoc を Python へ公開 (読み取り専用メンバ) */
  py::class_<SigLoc>(m, "SigLoc")
      .def_readonly("batch", &SigLoc::batch)
      .def_readonly("row", &SigLoc::row)
      .def_readonly("n_samples", &SigLoc::n_samples)
      .def_readonly("calibration_offset", &SigLoc::calibration_offset)
      .def_readonly("calibration_scale", &SigLoc::calibration_scale)
      .def("__repr__", [](SigLoc const &s) {
        return "<SigLoc b=" + std::to_string(s.batch) +
               " r=" + std::to_string(s.row) +
               " n=" + std::to_string(s.n_samples) + ">";
      });

  /* インデックス操作クラス */
  py::class_<PyPod5Index>(m, "Pod5Index")
      .def(py::init<std::string>(), py::arg("pod5_file"))
      .def("build_index", &PyPod5Index::build_index)
      .def("save_index", &PyPod5Index::save_index, py::arg("path"))
      .def("load_index", &PyPod5Index::load_index, py::arg("path"))
      .def("fetch_signal", &PyPod5Index::fetch_signal, py::arg("uuid"),
           "Return numpy int16 array")
      .def("get_calibration_offset", &PyPod5Index::get_calibration_offset)
      .def("get_calibration_scale", &PyPod5Index::get_calibration_scale)
      .def("get_calibration", &PyPod5Index::get_calibration,
           "Return (offset, scale) tuple for a given UUID")
      .def("get_signal_length", &PyPod5Index::get_signal_length,
           py::arg("uuid"), "Return signal length for a given UUID")
      .def(
          "list_read_ids",
          [](PyPod5Index &self) { return self.list_read_ids(); },
          "Return all read_id strings in the current index")
      .def("fetch_signals", &PyPod5Index::fetch_signals, py::arg("uuids"),
           "Fetch multiple signals in parallel, IO overlapped with numpy "
           "copy");
}


