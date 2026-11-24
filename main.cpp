#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/alpha_wrap_3.h>
#include <CGAL/Polygon_mesh_processing/IO/polygon_mesh_io.h>
#include <CGAL/Polygon_mesh_processing/bbox.h>
#include <CGAL/Real_timer.h>
#include <CGAL/Mesh_triangulation_3.h>
#include <CGAL/Mesh_complex_3_in_triangulation_3.h>
#include <CGAL/Mesh_criteria_3.h>
#include <CGAL/Polyhedral_mesh_domain_3.h>
#include <CGAL/make_mesh_3.h>
#include <CGAL/IO/output_to_vtu.h>
#include <CGAL/IO/File_medit.h>

#include <fstream>

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

using K = CGAL::Exact_predicates_inexact_constructions_kernel;
using Point_3 = K::Point_3;
using Mesh = CGAL::Surface_mesh<Point_3>;
namespace PMP = CGAL::Polygon_mesh_processing;

using Mesh_domain = CGAL::Polyhedral_mesh_domain_3<Mesh, K>;
using Tr = CGAL::Mesh_triangulation_3<Mesh_domain, CGAL::Default, CGAL::Sequential_tag>::type;
using C3t3 = CGAL::Mesh_complex_3_in_triangulation_3<Tr>;
using Mesh_criteria = CGAL::Mesh_criteria_3<Tr>;

static bool ends_with(const std::string& s, const std::string& suffix)
{
  return s.size() >= suffix.size() &&
         s.compare(s.size() - suffix.size(), suffix.size(), suffix) == 0;
}

// Fill the (closed) wrap with tetrahedra and write them as .mesh (Medit) or .vtu
static bool write_tets(const Mesh& wrap, double size, const std::string& file)
{
  namespace params = CGAL::parameters;
  Mesh_domain domain(wrap);
  Mesh_criteria criteria(params::facet_angle(25).facet_size(size).facet_distance(size / 10)
                             .cell_radius_edge_ratio(3).cell_size(size));
  C3t3 c3t3 = CGAL::make_mesh_3<C3t3>(domain, criteria,
                                      params::no_perturb().no_exude());

  std::cout << "Tet mesh: " << c3t3.triangulation().number_of_vertices() << " vertices, "
            << c3t3.number_of_cells_in_complex() << " tetrahedra\n";
  if(c3t3.number_of_cells_in_complex() == 0)
  {
    std::cerr << "Tet mesh is empty (try a larger --tet-size-ratio).\n";
    return false;
  }

  std::ofstream out(file);
  if(!out)
    return false;
  if(ends_with(file, ".vtu"))
    CGAL::IO::output_to_vtu(out, c3t3, CGAL::IO::ASCII);
  else
    CGAL::IO::write_MEDIT(out, c3t3);
  return static_cast<bool>(out);
}

static void usage(const char* prog)
{
  std::cerr << "Usage: " << prog << " input.off [options]\n"
            << "  --alpha-ratio R   alpha  = bbox_diagonal / R   (default 20)\n"
            << "  --offset-ratio R  offset = bbox_diagonal / R   (default 2000)\n"
            << "  --out FILE        output file                  (default wrap.off)\n"
            << "  --seed X Y Z      wrap the interior cavity containing this point;\n"
            << "                    may be repeated for several cavities\n"
            << "  --tets FILE       also fill the wrap with tetrahedra (.mesh or .vtu)\n"
            << "  --tet-size-ratio R  tet size = bbox_diagonal / R  (default 30)\n";
}

int main(int argc, char** argv)
{
  if(argc < 2)
  {
    usage(argv[0]);
    return EXIT_FAILURE;
  }

  const std::string input_file = argv[1];
  double alpha_ratio = 20.;
  double offset_ratio = 2000.;
  std::string output_file = "wrap.off";
  std::string tets_file;
  double tet_size_ratio = 30.;
  std::vector<Point_3> seeds;

  for(int i = 2; i < argc; ++i)
  {
    const std::string arg = argv[i];
    if(arg == "--alpha-ratio" && i + 1 < argc)
      alpha_ratio = std::atof(argv[++i]);
    else if(arg == "--offset-ratio" && i + 1 < argc)
      offset_ratio = std::atof(argv[++i]);
    else if(arg == "--out" && i + 1 < argc)
      output_file = argv[++i];
    else if(arg == "--tets" && i + 1 < argc)
      tets_file = argv[++i];
    else if(arg == "--tet-size-ratio" && i + 1 < argc)
      tet_size_ratio = std::atof(argv[++i]);
    else if(arg == "--seed" && i + 3 < argc)
    {
      const double x = std::atof(argv[++i]);
      const double y = std::atof(argv[++i]);
      const double z = std::atof(argv[++i]);
      seeds.emplace_back(x, y, z);
    }
    else
    {
      std::cerr << "Unknown or incomplete option: " << arg << "\n";
      usage(argv[0]);
      return EXIT_FAILURE;
    }
  }

  Mesh input;
  if(!PMP::IO::read_polygon_mesh(input_file, input) || is_empty(input))
  {
    std::cerr << "Failed to read a valid input mesh: " << input_file << "\n";
    return EXIT_FAILURE;
  }
  std::cout << "Read " << num_vertices(input) << " vertices, "
            << num_faces(input) << " faces\n";

  const CGAL::Bbox_3 bbox = PMP::bbox(input);
  const double diag = std::sqrt(CGAL::square(bbox.xmax() - bbox.xmin()) +
                                CGAL::square(bbox.ymax() - bbox.ymin()) +
                                CGAL::square(bbox.zmax() - bbox.zmin()));
  const double alpha = diag / alpha_ratio;
  const double offset = diag / offset_ratio;
  std::cout << "alpha = " << alpha << ", offset = " << offset << "\n";

  CGAL::Real_timer t;
  t.start();
  Mesh wrap;
  if(seeds.empty())
  {
    CGAL::alpha_wrap_3(input, alpha, offset, wrap);
  }
  else
  {
    std::cout << "Interior wrap from " << seeds.size() << " seed(s)\n";
    CGAL::alpha_wrap_3(input, alpha, offset, wrap,
                       CGAL::parameters::seed_points(seeds));
  }
  t.stop();

  if(is_empty(wrap))
  {
    std::cerr << "Wrap is empty. If using --seed, make sure the point lies in "
                 "empty space inside the cavity.\n";
    return EXIT_FAILURE;
  }

  std::cout << "Result: " << num_vertices(wrap) << " vertices, "
            << num_faces(wrap) << " faces in " << t.time() << " s\n";

  if(!CGAL::IO::write_polygon_mesh(output_file, wrap,
                                   CGAL::parameters::stream_precision(17)))
  {
    std::cerr << "Failed to write " << output_file << "\n";
    return EXIT_FAILURE;
  }
  std::cout << "Wrote " << output_file << "\n";

  if(!tets_file.empty())
  {
    if(!write_tets(wrap, diag / tet_size_ratio, tets_file))
    {
      std::cerr << "Failed to write tetrahedral mesh " << tets_file << "\n";
      return EXIT_FAILURE;
    }
    std::cout << "Wrote " << tets_file << "\n";
  }
  return EXIT_SUCCESS;
}
