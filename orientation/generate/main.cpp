#include <fstream>
#include <string>
#include <iostream>
#include <chrono>
#include <iomanip>

#include "../sim/backend.hpp"
#include "../sim/algebra.hpp"

#define CADENCE 1200.0 // Seconds between record

int main(int argc, char* argv[]) {
    // Open files
    std::string filename = "2-params.dat";
    if (argc >= 2) {
        filename = std::string(argv[1]);
    }

    if (filename.size() < 4 ||
        filename.substr(filename.size() - 4, 4) != ".dat") {
        std::cout << "The input file must be a .dat file." << std::endl;
        return 0;
    }
    std::string bare = filename.substr(0, filename.size() - 4);

    std::ifstream test;
    test.open(filename);
    if (!test.is_open()) {
        std::cout << "The file " << filename << " does not exist." << std::endl;
    }

    // Load information
    /* Note: since this code is intended to be used in a limited set of
     * scnarios, and since I will always have access to this source code
     * to debug any errors. I will not be writing a "safe parser". That is,
     * when I parse the file `filename`, I will not carefully print out the
     * error messages that could occur. The program will crash somehow and it
     * is up to the user to figure out the problem with the formatting of
     * `filename`. I'm doing this to save time. */

    std::ifstream f;
    f.open(filename);
    std::string line, word, x, y, z;
    std::istringstream ss;

    // Max ls
    std::getline(f, line);
    ss = std::istringstream (line);
    ss >> x;
    ss >> y;
    uint maxjl = std::stoi(x);
    uint maxkl = std::stoi(y);

    assert(maxjl == ASTEROIDS_MAX_J);
    assert(maxkl == ASTEROIDS_MAX_K);

    // Jlms
    std::vector<cdouble> halfjlms;// 22, 21, 20, 33, 32, 31, 30
    for (uint l = 0; l <= maxjl; l++){
        std::getline(f, line);
        ss = std::istringstream (line);
        for (int m = -l; m < (int)l; m+=2) {
            ss >> x >> y;
            halfjlms.push_back({std::stod(x), std::stod(y)});
        }
        ss >> x;
        halfjlms.push_back({std::stod(x), 0});
    }

    // Mlms
    std::vector<cdouble> halfklms;
    for (uint l = 0; l <= maxkl; l++){
        std::getline(f, line);
        ss = std::istringstream (line);
        for (int m = -l; m < (int)l; m+=2) {
            ss >> x >> y;
            halfklms.push_back({std::stod(x), std::stod(y)});
        }
        ss >> x;
        halfklms.push_back({std::stod(x), 0});
    }

    // Radius
    std::getline(f, line);
    ss = std::istringstream (line);
    ss >> word;
    double radius = std::stod(word);

    // Spin
    std::getline(f, line);
    ss = std::istringstream (line);
    ss >> x >> y >> z;
    Vector3 spin = Vector3({std::stod(x), std::stod(y), std::stod(z)});

    // Initial roll
    std::getline(f, line);
    ss = std::istringstream (line);
    ss >> word;
    double initial_roll = std::stod(word);

    // Impact parameter
    std::getline(f, line);
    ss = std::istringstream (line);
    ss >> word;
    double impact_parameter = std::stod(word);

    // Velocity (units: times escape velocity)
    std::getline(f, line);
    ss = std::istringstream (line);
    ss >> word;
    double speed = std::stod(word);

    cdouble jlms[(ASTEROIDS_MAX_J+1) * (ASTEROIDS_MAX_J+1)];
    cdouble klms[(ASTEROIDS_MAX_K+1) * (ASTEROIDS_MAX_K+1)];
    uint j = 0;
    for (uint l = 0; l <= ASTEROIDS_MAX_J; l++) {
        for (int m = -l; m <= (int)l; m++) {
            assert(j < (ASTEROIDS_MAX_J+1) * (ASTEROIDS_MAX_J+1));
            if (m < 0) {
                jlms[j] = halfjlms[l * (l + 1) / 2 + l - abs(m)].conj()
                    * (double)parity(m);
            }
            else {
                jlms[j] = halfjlms[l * (l + 1) / 2 + l - abs(m)];
            }
            j++;
        }
    }
    uint k = 0;
    for (uint l = 0; l <= ASTEROIDS_MAX_K; l++) {
        for (int m = -l; m <= (int)l; m++) {
            assert(k < (ASTEROIDS_MAX_K+1) * (ASTEROIDS_MAX_K+1));
            if (m < 0) {
                klms[k] = halfklms[l * (l + 1) / 2 + l - abs(m)].conj()
                    * (double)parity(m);
            }
            else {
                klms[k] = halfklms[l * (l + 1) / 2 + l - abs(m)];
            }
            k++;
        }
    }


    // Load asteroid
    Asteroid asteroid(&jlms[0], &klms[0], radius, spin, initial_roll, impact_parameter, speed, 6.67e-11 * 5.97e24, 6371000, 0, false, 1);

    // Run asteroid
    std::vector<double> resolved_data;
    auto start = std::chrono::high_resolution_clock::now();

    int frames = asteroid.simulate(CADENCE, resolved_data);

    auto stop = std::chrono::high_resolution_clock::now();
    double time_taken = std::chrono::duration_cast<std::chrono::milliseconds>(
        stop - start).count() / 1000.0;

    std::cout << "Simulation took " << frames << " frames or "
        << time_taken << " s." << std::endl;

    std::ofstream resolved_file;
    resolved_file.open(bare + "-resolved.dat");
    for (uint i = 0; i < resolved_data.size(); i+=4) {
        resolved_file << std::setprecision(17) << resolved_data[i] << ' ';
        resolved_file << std::setprecision(17) << resolved_data[i + 1] << ' ';
        resolved_file << std::setprecision(17) << resolved_data[i + 2] << ' ';
        resolved_file << std::setprecision(17) << resolved_data[i + 3] << std::endl;
    }

    return 1;
}
