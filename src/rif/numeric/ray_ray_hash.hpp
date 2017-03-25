#ifndef INCLUDED_numeric_ray_ray_hash_HH
#define INCLUDED_numeric_ray_ray_hash_HH

#include <iostream>
#include <numeric/Ray.hpp>
#include <numeric/bcc_lattice.hpp>
#include <numeric/cube_to_sphere.hpp>
#include <numeric/types.hpp>
#include <util/SimpleArray.hpp>

namespace rif {
namespace numeric {

///@brief
///@detail

/**
 * @brief       Align rays to ray a's canonical position
 *
 * @param[in]  a     ray1
 * @param[in]  b     ray2
 *
 * @tparam     F     float type
 *
 * @return     Ray b aligned to Ray a's canonical position
 * @detail     canonical position places r at the origin along x and s in the
 * x,y plane
 */
template <class F>
Ray<F> align_ray_pair(Ray<F> a, Ray<F> b) {
  // todo: should this be made symmetrical???
  M3<F> rotation;
  V3<F> basis1 = a.direction;
  V3<F> basis3 = basis1.cross(b.origin - a.origin).normalized();
  V3<F> basis2 = basis3.cross(basis1).normalized();
  rotation.row(0) = basis1;
  rotation.row(1) = basis2;
  rotation.row(2) = basis3;
  V3<F> a2_origin = rotation * a.origin;
  Ray<F> b2 = rotation * b;
  b2.origin -= a2_origin;
  // std::cout << rotation.determinant() << std::endl;
  // Ray<F> a2 = rotation * a;
  // std::cout << "a  " << a << std::endl;
  // std::cout << "b  " << b << std::endl;
  // std::cout << "a2 " << a2 << std::endl;
  // std::cout << "b2 " << b2 << std::endl;
  return b2;
}

///@brief get num cells for quadsphere
template <class F>
int qs_nc(F resl, F lever) {
  // TODO: audit this fudge factor
  return std::max(F(1), lever / resl * F(1.5));
}
template <class F>
F qs_bound(F resl, F lever) {
  return 1.0 - 0.25 / qs_nc(resl, lever);
}

template <class R = Ray<float>, class _K = uint32_t>
struct RayBins {
  using F = typename R::Scalar;
  using K = _K;
  using Grid = BCC<4, F, K>;
  using F4 = typename Grid::Floats;
  using V = typename R::V;
  util::SimpleArray<6, Grid> bcc_;
  RayBins(F resl = 0.25, F lever = 1.5, F cartbound = 128)
      : bcc_(Grid(I4(2 * cartbound / resl, 2 * cartbound / resl,
                     qs_nc(resl, lever), qs_nc(resl, lever)),
                  F4(-cartbound, -cartbound, -qs_bound(resl, lever),
                     -qs_bound(resl, lever)),
                  F4(+cartbound, +cartbound, +qs_bound(resl, lever),
                     +qs_bound(resl, lever)))) {
    assert(sizes[2] == sizes[3]);
  }
  K get_key(R a, R b) const { return get_key(align_ray_pair(a, b)); }
  K get_key(R r) const {
    assert(fabs(r.origin[2]) < 0.001);
    // std::cout << "get_key: " << r << std::endl;
    F x, y;
    K face = get_quadsphere_coords(r.direction, x, y);
    F4 bcrd(r.origin[0], r.origin[1], x, y);
    // std::cout << "get_key: " << bcrd << std::endl;
    K bcc_key = bcc_[face][bcrd];
    // std::cout << "get_key: " << face << " " << bcc_key << std::endl;
    return face * bcc_[face].size() + bcc_key;
  }
  R get_center(K k) const {
    K face = k / bcc_[face].size();
    K bcc_key = k % bcc_[face].size();
    // std::cout << "get_cen: " << face << " " << bcc_key << std::endl;
    F4 bcrd = bcc_[face][bcc_key];
    // std::cout << "get_cen: " << bcrd << std::endl;
    auto dir = get_point_from_quadsphere_coords<V>(face, bcrd[2], bcrd[3]);
    R r(V(bcrd[0], bcrd[1], 0.0), dir);
    return r;
  }
  A2<F> brute_maxmin_nbr(bool face0_only = false) const {
    int nface = face0_only ? 1 : 6;
    F maxmindot = -9e9, maxmindis = -9e9;
    for (int i = 0; i < bcc_[0].size() * nface - 1; ++i) {
      R a = get_center(i);
      F mindot = 9e9;
      F mindis = 9e9;
      for (int j = i + 1; j < bcc_[0].size() * nface; ++j) {
        R b = get_center(j);
        mindot = std::min(mindot, a.direction.dot(b.direction));
        F dis = (a.origin - b.origin).norm();
        if (dis > 0.0001) mindis = std::min(mindis, dis);
      }
      maxmindot = std::max(maxmindot, mindot);
      maxmindis = std::max(maxmindis, mindis);
    }
    return A2<F>(maxmindis, acos(maxmindot));
  }
  uint size() const { return 6 * bcc_[0].size(); }
  uint size_cart() const { return bcc_[0].nside_[0]; }
  uint size_qsph() const { return bcc_[0].nside_[2]; }
};
}
}

#endif