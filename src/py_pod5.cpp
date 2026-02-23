#include "pod5_format/c_api.h"
#include "pod5_signal_index.hpp"

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;
using namespace pod5;

/* ========================================================================== */
/*  ラッパークラス                                                             */
/* ========================================================================== */
class PyPod5Index {
public:
  /// @brief pod5 ファイルを開く。
  explicit PyPod5Index(const std::string &file) {
    if (pod5_init() != POD5_OK)
      throw std::runtime_error("pod5_init failed");
    reader_ = pod5_open_file(file.c_str());
    if (!reader_)
      throw std::runtime_error("pod5_open_file failed");
  }

  ~PyPod5Index() {
    if (reader_)
      pod5_close_and_free_reader(reader_);
    pod5_terminate();
  }

  /// @brief Read Table を走査してインデックスを構築する。
  void build_index() {
    py::gil_scoped_release release;
    idx_ = pod5::build_signal_index(reader_);
  }

  /// @brief インデックスをバイナリファイルに保存する。
  void save_index(const std::string &path) const {
    py::gil_scoped_release release;
    pod5::save_index_bin(idx_, path);
  }

  /// @brief バイナリファイルからインデックスを読み込む。
  void load_index(const std::string &path) {
    py::gil_scoped_release release;
    idx_ = pod5::load_index_bin(path);
  }

  /// @brief UUID を指定してシグナルを取得する（Signal Table 直接アクセス）。
  py::array_t<int16_t> fetch_signal(py::object uuid) const {
    ReadId id = to_read_id(uuid);
    std::vector<int16_t> buf;
    {
      py::gil_scoped_release release;
      auto it = idx_.find(id);
      if (it == idx_.end())
        throw std::out_of_range("UUID not in index");
      buf = pod5::fetch_signal(reader_, it->second);
    }
    auto arr = py::array_t<int16_t>(buf.size());
    std::memcpy(arr.mutable_data(), buf.data(), buf.size() * sizeof(int16_t));
    return arr;
  }

  /// @brief UUID を指定して pA キャリブレーション済みシグナルを取得する。
  py::array_t<float> fetch_pA_signal(py::object uuid) const {
    ReadId id = to_read_id(uuid);
    std::vector<float> buf;
    {
      py::gil_scoped_release release;
      auto it = idx_.find(id);
      if (it == idx_.end())
        throw std::out_of_range("UUID not in index");
      buf = pod5::fetch_pA_signal(reader_, it->second);
    }
    auto arr = py::array_t<float>(buf.size());
    std::memcpy(arr.mutable_data(), buf.data(), buf.size() * sizeof(float));
    return arr;
  }

  /// @brief UUID のキャリブレーション情報を (offset, scale) タプルで返す。
  py::tuple get_calibration(py::object uuid) const {
    ReadId id = to_read_id(uuid);
    auto it = idx_.find(id);
    if (it == idx_.end())
      throw std::out_of_range("UUID not in index");
    return py::make_tuple(it->second.calibration_offset,
                          it->second.calibration_scale);
  }

  /// @brief UUID のキャリブレーションオフセットを返す。
  float get_calibration_offset(py::object uuid) const {
    ReadId id = to_read_id(uuid);
    auto it = idx_.find(id);
    if (it == idx_.end())
      throw std::out_of_range("UUID not in index");
    return it->second.calibration_offset;
  }

  /// @brief UUID のキャリブレーションスケールを返す。
  float get_calibration_scale(py::object uuid) const {
    ReadId id = to_read_id(uuid);
    auto it = idx_.find(id);
    if (it == idx_.end())
      throw std::out_of_range("UUID not in index");
    return it->second.calibration_scale;
  }

  /// @brief UUID のシグナル長（サンプル数）を返す。
  size_t get_signal_length(py::object uuid) const {
    ReadId id = to_read_id(uuid);
    auto it = idx_.find(id);
    if (it == idx_.end())
      throw std::out_of_range("UUID not in index");
    return it->second.n_samples;
  }

  /// @brief インデックス内の全 read_id を文字列リストで返す。
  std::vector<std::string> list_read_ids() const {
    std::vector<std::string> out;
    out.reserve(idx_.size());
    char buf[37];
    for (auto const &[key, _] : idx_) {
      pod5_format_read_id(key.data(), buf);
      out.emplace_back(buf);
    }
    return out;
  }

  /// @brief UUID リストを Signal Table 上の物理位置順にソートして返す。
  py::list sort_uuids_by_location(py::iterable const &uuid_list) const {
    std::vector<ReadId> ids;
    std::vector<py::object> originals;
    for (auto h : uuid_list) {
      auto obj = h.cast<py::object>();
      originals.push_back(obj);
      ids.push_back(to_read_id(obj));
    }

    auto order = pod5::sort_by_location(idx_, ids);

    py::list result;
    for (size_t i : order) {
      result.append(originals[i]);
    }
    return result;
  }

  /// @brief UUID リストの signal_row_start を一括取得する（numpy uint64 配列）。
  py::array_t<uint64_t>
  get_signal_row_starts(py::iterable const &uuid_list) const {
    std::vector<uint64_t> starts;
    for (auto h : uuid_list) {
      ReadId id = to_read_id(h.cast<py::object>());
      auto it = idx_.find(id);
      if (it == idx_.end())
        throw std::out_of_range("UUID not in index");
      starts.push_back(it->second.signal_row_start);
    }
    auto arr = py::array_t<uint64_t>(starts.size());
    std::memcpy(arr.mutable_data(), starts.data(),
                starts.size() * sizeof(uint64_t));
    return arr;
  }

private:
  Pod5FileReader_t *reader_{nullptr};
  SignalIndex idx_;

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
/*  pybind11 モジュール定義                                                    */
/* ========================================================================== */
PYBIND11_MODULE(pod5_random_access_pybind, m) {
  m.doc() = "POD5 signal-index with direct Signal Table access";

  py::class_<SigLoc>(m, "SigLoc")
      .def_readonly("signal_row_start", &SigLoc::signal_row_start)
      .def_readonly("signal_row_count", &SigLoc::signal_row_count)
      .def_readonly("n_samples", &SigLoc::n_samples)
      .def_readonly("calibration_offset", &SigLoc::calibration_offset)
      .def_readonly("calibration_scale", &SigLoc::calibration_scale)
      .def("__repr__", [](SigLoc const &s) {
        return "<SigLoc start=" + std::to_string(s.signal_row_start) +
               " count=" + std::to_string(s.signal_row_count) +
               " n=" + std::to_string(s.n_samples) + ">";
      });

  py::class_<PyPod5Index>(m, "Pod5Index")
      .def(py::init<std::string>(), py::arg("pod5_file"))
      .def("build_index", &PyPod5Index::build_index,
           "Read Table を走査してインデックスを構築")
      .def("save_index", &PyPod5Index::save_index, py::arg("path"),
           "インデックスをバイナリファイルに保存")
      .def("load_index", &PyPod5Index::load_index, py::arg("path"),
           "バイナリファイルからインデックスを読み込み")
      .def("fetch_signal", &PyPod5Index::fetch_signal, py::arg("uuid"),
           "Signal Table から直接シグナルを取得 (numpy int16 array)")
      .def("fetch_pA_signal", &PyPod5Index::fetch_pA_signal, py::arg("uuid"),
           "pA キャリブレーション済みシグナルを取得 (numpy float32 array)")
      .def("get_calibration", &PyPod5Index::get_calibration, py::arg("uuid"),
           "インデックスから (offset, scale) タプルを返す")
      .def("get_calibration_offset", &PyPod5Index::get_calibration_offset,
           py::arg("uuid"))
      .def("get_calibration_scale", &PyPod5Index::get_calibration_scale,
           py::arg("uuid"))
      .def("get_signal_length", &PyPod5Index::get_signal_length,
           py::arg("uuid"), "インデックスからシグナル長を返す")
      .def("list_read_ids",
           [](PyPod5Index &self) { return self.list_read_ids(); },
           "インデックス内の全 read_id 文字列を返す")
      .def("sort_uuids_by_location", &PyPod5Index::sort_uuids_by_location,
           py::arg("uuids"),
           "UUID リストを Signal Table 上の物理位置順にソート")
      .def("get_signal_row_starts", &PyPod5Index::get_signal_row_starts,
           py::arg("uuids"),
           "UUID リストの signal_row_start を一括取得 (numpy uint64 array)");
}
