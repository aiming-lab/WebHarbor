#!/usr/bin/env python3
"""Build-time seed data for the NVIDIA mirror.

All consumed by the gated seed_*() functions in app.py. Specs reflect real
NVIDIA published figures. Image paths are relative to static/images/.
"""
from datetime import date

# --------------------------------------------------------------------------
# Products — GPUs / hardware across five categories
# --------------------------------------------------------------------------
def _p(slug, name, category, series, price, tagline, description, image=None,
       featured=False, year=2025, in_stock=True, **specs):
    return dict(
        slug=slug, name=name, category=category, series=series, price_usd=price,
        tagline=tagline, description=description,
        image=image or f"products/{slug}.png", is_featured=featured,
        release_year=year, in_stock=in_stock,
        architecture=specs.get('architecture', ''),
        cuda_cores=specs.get('cuda_cores'),
        tensor_cores=specs.get('tensor_cores'),
        rt_cores=specs.get('rt_cores'),
        memory_gb=specs.get('memory_gb'),
        memory_type=specs.get('memory_type', ''),
        memory_bandwidth=specs.get('memory_bandwidth', ''),
        boost_clock_ghz=specs.get('boost_clock_ghz'),
        tdp_watts=specs.get('tdp_watts'),
        interface=specs.get('interface', ''),
        recommended_psu_watts=specs.get('recommended_psu_watts'),
    )


PRODUCTS = [
    # ---- GeForce Gaming — RTX 50 Series (Blackwell) ----
    _p("geforce-rtx-5090", "GeForce RTX 5090", "GeForce Gaming", "RTX 50 Series",
       1999, "The most powerful GeForce GPU ever built.",
       "Powered by the NVIDIA Blackwell architecture and DLSS 4, the GeForce RTX 5090 "
       "delivers unprecedented gaming and creator performance with 32 GB of GDDR7 memory.",
       featured=True, year=2025, architecture="Blackwell", cuda_cores=21760,
       tensor_cores=680, rt_cores=170, memory_gb=32, memory_type="GDDR7",
       memory_bandwidth="1792 GB/s", boost_clock_ghz=2.41, tdp_watts=575,
       interface="PCIe 5.0", recommended_psu_watts=1000),
    _p("geforce-rtx-5080", "GeForce RTX 5080", "GeForce Gaming", "RTX 50 Series",
       999, "Game-changing performance with DLSS 4.",
       "The GeForce RTX 5080 brings Blackwell efficiency, GDDR7 memory, and full ray "
       "tracing to high-refresh 4K gaming.",
       featured=True, year=2025, architecture="Blackwell", cuda_cores=10752,
       tensor_cores=336, rt_cores=84, memory_gb=16, memory_type="GDDR7",
       memory_bandwidth="960 GB/s", boost_clock_ghz=2.62, tdp_watts=360,
       interface="PCIe 5.0", recommended_psu_watts=850),
    _p("geforce-rtx-5070-ti", "GeForce RTX 5070 Ti", "GeForce Gaming", "RTX 50 Series",
       749, "Elevated 1440p and 4K play.",
       "16 GB of GDDR7 and Blackwell tensor cores make the RTX 5070 Ti a sweet spot for "
       "high-frame-rate gaming with DLSS 4 Multi Frame Generation.",
       year=2025, architecture="Blackwell", cuda_cores=8960, tensor_cores=280,
       rt_cores=70, memory_gb=16, memory_type="GDDR7", memory_bandwidth="896 GB/s",
       boost_clock_ghz=2.45, tdp_watts=300, interface="PCIe 5.0",
       recommended_psu_watts=750),
    _p("geforce-rtx-5070", "GeForce RTX 5070", "GeForce Gaming", "RTX 50 Series",
       549, "RTX 4090 performance at a fraction of the power.",
       "The RTX 5070 pairs 12 GB of GDDR7 with DLSS 4 to deliver flagship-class frames "
       "in today's most demanding titles.",
       featured=True, year=2025, architecture="Blackwell", cuda_cores=6144,
       tensor_cores=192, rt_cores=48, memory_gb=12, memory_type="GDDR7",
       memory_bandwidth="672 GB/s", boost_clock_ghz=2.51, tdp_watts=250,
       interface="PCIe 5.0", recommended_psu_watts=650),
    _p("geforce-rtx-5060-ti", "GeForce RTX 5060 Ti", "GeForce Gaming", "RTX 50 Series",
       429, "Mainstream gaming, supercharged.",
       "With 16 GB of GDDR7, the RTX 5060 Ti makes high-fidelity 1440p gaming and local "
       "AI workloads accessible.",
       year=2025, architecture="Blackwell", cuda_cores=4608, tensor_cores=144,
       rt_cores=36, memory_gb=16, memory_type="GDDR7", memory_bandwidth="448 GB/s",
       boost_clock_ghz=2.57, tdp_watts=180, interface="PCIe 5.0",
       recommended_psu_watts=550),
    _p("geforce-rtx-5060", "GeForce RTX 5060", "GeForce Gaming", "RTX 50 Series",
       299, "DLSS 4 for every gamer.",
       "The RTX 5060 brings Blackwell and DLSS 4 to the most popular price point in PC gaming.",
       year=2025, architecture="Blackwell", cuda_cores=3840, tensor_cores=120,
       rt_cores=30, memory_gb=8, memory_type="GDDR7", memory_bandwidth="448 GB/s",
       boost_clock_ghz=2.50, tdp_watts=145, interface="PCIe 5.0",
       recommended_psu_watts=450),
    # ---- GeForce Gaming — RTX 40 Series (Ada Lovelace) ----
    _p("geforce-rtx-4090", "GeForce RTX 4090", "GeForce Gaming", "RTX 40 Series",
       1599, "Beyond fast. The Ada Lovelace flagship.",
       "24 GB of GDDR6X and 16,384 CUDA cores made the RTX 4090 the definitive 4K and "
       "creator GPU of the Ada generation.",
       year=2022, architecture="Ada Lovelace", cuda_cores=16384, tensor_cores=512,
       rt_cores=128, memory_gb=24, memory_type="GDDR6X", memory_bandwidth="1008 GB/s",
       boost_clock_ghz=2.52, tdp_watts=450, interface="PCIe 4.0",
       recommended_psu_watts=850),
    _p("geforce-rtx-4080-super", "GeForce RTX 4080 SUPER", "GeForce Gaming", "RTX 40 Series",
       999, "Enthusiast 4K with Ada efficiency.",
       "The RTX 4080 SUPER delivers high-refresh 4K gaming and creator acceleration with "
       "16 GB of fast GDDR6X.",
       year=2024, architecture="Ada Lovelace", cuda_cores=10240, tensor_cores=320,
       rt_cores=80, memory_gb=16, memory_type="GDDR6X", memory_bandwidth="736 GB/s",
       boost_clock_ghz=2.55, tdp_watts=320, interface="PCIe 4.0",
       recommended_psu_watts=750),
    _p("geforce-rtx-4070-super", "GeForce RTX 4070 SUPER", "GeForce Gaming", "RTX 40 Series",
       599, "Seriously fast 1440p.",
       "More cores than the original RTX 4070 plus DLSS 3 Frame Generation make the 4070 "
       "SUPER an outstanding 1440p performer.",
       year=2024, architecture="Ada Lovelace", cuda_cores=7168, tensor_cores=224,
       rt_cores=56, memory_gb=12, memory_type="GDDR6X", memory_bandwidth="504 GB/s",
       boost_clock_ghz=2.48, tdp_watts=220, interface="PCIe 4.0",
       recommended_psu_watts=650),
    _p("geforce-rtx-4060", "GeForce RTX 4060", "GeForce Gaming", "RTX 40 Series",
       299, "The most popular way into RTX.",
       "Efficient Ada Lovelace gaming with DLSS 3 at 1080p, sipping just 115 W.",
       year=2023, architecture="Ada Lovelace", cuda_cores=3072, tensor_cores=96,
       rt_cores=24, memory_gb=8, memory_type="GDDR6", memory_bandwidth="272 GB/s",
       boost_clock_ghz=2.46, tdp_watts=115, interface="PCIe 4.0",
       recommended_psu_watts=550),

    # ---- Studio / Professional (RTX workstation) ----
    _p("rtx-pro-6000-blackwell", "RTX PRO 6000 Blackwell", "Studio / Professional",
       "RTX PRO Blackwell", 8565, "The ultimate workstation GPU.",
       "96 GB of GDDR7 and the Blackwell architecture power the most demanding AI, "
       "rendering, and simulation workloads in professional workstations.",
       featured=True, year=2025, architecture="Blackwell", cuda_cores=24064,
       memory_gb=96, memory_type="GDDR7 ECC", memory_bandwidth="1792 GB/s",
       tdp_watts=600, interface="PCIe 5.0"),
    _p("rtx-6000-ada", "RTX 6000 Ada Generation", "Studio / Professional",
       "RTX Ada", 6800, "Workstation performance for rendering and AI.",
       "48 GB of ECC GDDR6 and Ada Lovelace cores deliver massive throughput for "
       "visualization, simulation, and AI development.",
       year=2022, architecture="Ada Lovelace", cuda_cores=18176, memory_gb=48,
       memory_type="GDDR6 ECC", memory_bandwidth="960 GB/s", tdp_watts=300,
       interface="PCIe 4.0"),
    _p("rtx-5000-ada", "RTX 5000 Ada Generation", "Studio / Professional",
       "RTX Ada", 4000, "Pro-grade power in a 250 W envelope.",
       "32 GB of ECC memory for large scenes, multi-app workflows, and AI inference at "
       "the desk.",
       year=2023, architecture="Ada Lovelace", cuda_cores=12800, memory_gb=32,
       memory_type="GDDR6 ECC", memory_bandwidth="576 GB/s", tdp_watts=250,
       interface="PCIe 4.0"),
    _p("rtx-4000-ada", "RTX 4000 Ada Generation", "Studio / Professional",
       "RTX Ada", 1250, "Compact, single-slot pro acceleration.",
       "20 GB of memory in a single-slot, 130 W card for space-constrained workstations.",
       year=2023, architecture="Ada Lovelace", cuda_cores=6144, memory_gb=20,
       memory_type="GDDR6 ECC", memory_bandwidth="360 GB/s", tdp_watts=130,
       interface="PCIe 4.0"),

    # ---- Data Center / AI (price = contact sales) ----
    _p("dgx-b200", "NVIDIA Blackwell B200", "Data Center", "Blackwell",
       None, "The engine of the AI factory.",
       "The B200 Tensor Core GPU delivers a generational leap for trillion-parameter "
       "training and inference with 192 GB of HBM3e.",
       featured=True, year=2025, architecture="Blackwell", memory_gb=192,
       memory_type="HBM3e", memory_bandwidth="8 TB/s", tdp_watts=1000,
       interface="SXM"),
    _p("h200-tensor-core", "NVIDIA H200 Tensor Core GPU", "Data Center", "Hopper",
       None, "Supercharged generative AI and HPC.",
       "The H200 is the first GPU with 141 GB of HBM3e, nearly doubling capacity and "
       "boosting bandwidth to 4.8 TB/s for LLM inference.",
       featured=True, year=2024, architecture="Hopper", memory_gb=141,
       memory_type="HBM3e", memory_bandwidth="4.8 TB/s", tdp_watts=700,
       interface="SXM"),
    _p("h100-tensor-core", "NVIDIA H100 Tensor Core GPU", "Data Center", "Hopper",
       None, "The proven workhorse of modern AI.",
       "With the Transformer Engine and 80 GB of HBM3, the H100 accelerates LLM training "
       "and inference at data-center scale.",
       year=2022, architecture="Hopper", memory_gb=80, memory_type="HBM3",
       memory_bandwidth="3.35 TB/s", tdp_watts=700, interface="SXM"),
    _p("a100-tensor-core", "NVIDIA A100 Tensor Core GPU", "Data Center", "Ampere",
       None, "The data-center GPU that defined AI scale.",
       "80 GB of HBM2e and Multi-Instance GPU make the A100 a versatile platform for "
       "training, inference, and HPC.",
       year=2020, architecture="Ampere", memory_gb=80, memory_type="HBM2e",
       memory_bandwidth="2039 GB/s", tdp_watts=400, interface="SXM"),
    _p("l40s", "NVIDIA L40S", "Data Center", "Ada",
       None, "Universal GPU for AI, graphics, and video.",
       "48 GB of GDDR6 and Ada Lovelace cores make the L40S a versatile data-center GPU "
       "for inference, fine-tuning, and rendering.",
       year=2023, architecture="Ada Lovelace", cuda_cores=18176, memory_gb=48,
       memory_type="GDDR6", memory_bandwidth="864 GB/s", tdp_watts=350,
       interface="PCIe 4.0"),
    _p("gh200-grace-hopper", "NVIDIA GH200 Grace Hopper Superchip", "Data Center",
       "Grace Hopper", None, "CPU and GPU, coherently fused.",
       "The GH200 connects a Grace CPU and Hopper GPU over NVLink-C2C for giant-model AI "
       "and HPC with up to 624 GB of fast memory.",
       year=2024, architecture="Grace Hopper", memory_gb=144, memory_type="HBM3e",
       memory_bandwidth="4.9 TB/s", tdp_watts=1000, interface="NVLink-C2C"),

    # ---- Embedded / Edge (Jetson) ----
    _p("jetson-orin-nano-super", "Jetson Orin Nano Super Developer Kit", "Embedded",
       "Jetson Orin", 249, "The world's most affordable generative AI computer.",
       "67 TOPS of AI performance in a tiny module — the Jetson Orin Nano Super powers "
       "edge robotics, vision, and on-device LLMs.",
       featured=True, year=2024, architecture="Ampere", cuda_cores=1024,
       memory_gb=8, memory_type="LPDDR5", memory_bandwidth="102 GB/s", tdp_watts=25,
       interface="—"),
    _p("jetson-agx-orin", "Jetson AGX Orin 64GB", "Embedded", "Jetson Orin",
       1999, "Server-class AI at the edge.",
       "Up to 275 TOPS and 64 GB of memory bring advanced robotics and autonomous machine "
       "workloads to a 60 W module.",
       year=2022, architecture="Ampere", cuda_cores=2048, memory_gb=64,
       memory_type="LPDDR5", memory_bandwidth="204 GB/s", tdp_watts=60, interface="—"),
    _p("jetson-orin-nx", "Jetson Orin NX 16GB", "Embedded", "Jetson Orin",
       699, "Compact power for autonomous machines.",
       "100 TOPS in a small module for drones, robots, and smart cameras.",
       year=2023, architecture="Ampere", cuda_cores=1024, memory_gb=16,
       memory_type="LPDDR5", memory_bandwidth="102 GB/s", tdp_watts=25, interface="—"),

    # ---- Consumer Devices (SHIELD) ----
    _p("shield-tv-pro", "SHIELD TV Pro", "Consumer Devices", "SHIELD",
       199, "The ultimate 4K HDR streaming media player.",
       "AI-enhanced 4K upscaling, Dolby Vision and Atmos, and Google TV — powered by the "
       "NVIDIA Tegra X1+ processor.",
       featured=True, year=2019, architecture="Tegra X1+", memory_gb=3,
       memory_type="LPDDR4", tdp_watts=40, interface="HDMI 2.0b"),
    _p("shield-tv", "SHIELD TV", "Consumer Devices", "SHIELD",
       149, "Compact 4K HDR streaming, supercharged by AI.",
       "A tube-shaped 4K HDR streamer with AI upscaling and the Tegra X1+ processor.",
       year=2019, architecture="Tegra X1+", memory_gb=2, memory_type="LPDDR4",
       tdp_watts=40, interface="HDMI 2.0b"),
]

# --------------------------------------------------------------------------
# News / blog articles
# --------------------------------------------------------------------------
ARTICLES = [
    dict(slug="top500-green500-supercomputers-isc-2026",
         title="NVIDIA Powers Over 400 of the World's 500 Fastest Supercomputers",
         category="AI Infrastructure", author="NVIDIA Newsroom", published=date(2026, 6, 23),
         image="news/top500-green500-supercomputers-isc-2026.png", read_minutes=5,
         excerpt="NVIDIA technologies power more than 400 of the world's 500 fastest "
                 "supercomputers — 81% of the TOP500.",
         body="At ISC 2026, the latest TOP500 list confirmed that NVIDIA technologies now "
              "power more than 400 of the world's 500 fastest supercomputers — 81% of the "
              "list. NVIDIA also dominates the Green500 ranking of the most energy-efficient "
              "systems, underscoring how accelerated computing delivers both performance and "
              "efficiency for the world's most demanding scientific workloads."),
    dict(slug="jupiter-exascale-supercomputing-science",
         title="At ISC, JUPITER Shows What Exascale Science Looks Like",
         category="AI Infrastructure", author="NVIDIA Newsroom", published=date(2026, 6, 22),
         image="news/jupiter-exascale-supercomputing-science.png", read_minutes=6,
         excerpt="Europe's first exascale supercomputer — running on NVIDIA Grace Hopper "
                 "Superchips — is mapping the brain, modeling climate, and advancing 6G AI.",
         body="JUPITER, Europe's first exascale supercomputer, is built on NVIDIA Grace "
              "Hopper Superchips. Researchers are using it to map the human brain, model "
              "climate systems, advance 6G AI research, and break scientific records — a "
              "showcase of what exascale-class accelerated computing makes possible."),
    dict(slug="ai-for-science-software-cuda",
         title="New NVIDIA AI Software Unlocks Scientific Discoveries",
         category="AI", author="NVIDIA Newsroom", published=date(2026, 6, 22),
         image="news/ai-for-science-software-cuda.png", read_minutes=5,
         excerpt="NVIDIA CUDA-X libraries, microservices and reference code accelerate AI "
                 "for science.",
         body="From materials simulation to experimental astronomy, new NVIDIA CUDA-X "
              "libraries, microservices, and reference workflows are accelerating AI for "
              "science. The tools help researchers move from data to discovery faster across "
              "physics, chemistry, biology, and astronomy."),
    dict(slug="nvidia-vera-cpu-los-alamos-national-laboratory",
         title="NVIDIA Vera CPU Opens the Way for Agentic Scientific AI at Los Alamos",
         category="AI Infrastructure", author="NVIDIA Newsroom", published=date(2026, 6, 22),
         image="news/nvidia-vera-cpu-los-alamos-national-laboratory.png", read_minutes=5,
         excerpt="Mission, Vision and Veritas supercomputers with Vera CPUs to advance "
                 "materials simulation, scientific AI agents and molecular design.",
         body="Los Alamos National Laboratory is deploying new Mission, Vision, and Veritas "
              "supercomputers powered by the NVIDIA Vera CPU. The systems will advance "
              "materials simulation, agentic scientific AI, and molecular design for national "
              "research priorities."),
    dict(slug="blackwell-mlperf-training-6-0",
         title="Fastest, Largest, Strongest: NVIDIA Blackwell Sweeps MLPerf Training 6.0",
         category="AI Infrastructure", author="NVIDIA Newsroom", published=date(2026, 6, 16),
         image="news/blackwell-mlperf-training-6-0.png", read_minutes=6,
         excerpt="NVIDIA delivers the performance, scale and reliability that frontier "
                 "training requires — in benchmarks and beyond.",
         body="In the latest MLPerf Training 6.0 results, the NVIDIA Blackwell platform "
              "swept every benchmark, delivering record performance at scale. The results "
              "demonstrate the throughput and reliability that frontier model training "
              "demands across the largest GPU clusters."),
    dict(slug="rtx-ai-garage-local-gemma-diffusion",
         title="NVIDIA Accelerates Google DeepMind's DiffusionGemma for Local AI",
         category="AI", author="NVIDIA Newsroom", published=date(2026, 6, 10),
         image="news/rtx-ai-garage-local-gemma-diffusion.png", read_minutes=5,
         excerpt="The new DiffusionGemma open model generates text in parallel and is "
                 "optimized to run locally on the NVIDIA RTX platform.",
         body="DiffusionGemma, a new open model from Google DeepMind, generates text in "
              "parallel rather than one token at a time. NVIDIA has optimized it to run "
              "locally on GeForce RTX and RTX PRO GPUs, bringing fast, private generative "
              "AI to the desktop."),
    dict(slug="eco-wave-power-ai-digital-twins",
         title="Eco Wave Power Turns Waves Into Watts With NVIDIA AI and Digital Twins",
         category="AI", author="NVIDIA Newsroom", published=date(2026, 6, 22),
         image="news/eco-wave-power-ai-digital-twins.png", read_minutes=4,
         excerpt="An NVIDIA Inception startup is developing wave-energy technology powered "
                 "by NVIDIA AI infrastructure and digital twins.",
         body="Eco Wave Power, part of the NVIDIA Inception program's Sustainable Futures "
              "initiative, is building wave-energy technology using NVIDIA AI infrastructure "
              "and Omniverse digital twins to simulate and optimize clean power generation "
              "from ocean waves."),
    dict(slug="halos-os-robotaxi-safety",
         title="For Robotaxis, Safety Must Be Built In, Not Bolted On",
         category="Driving", author="NVIDIA Newsroom", published=date(2026, 6, 10),
         image="news/halos-os-robotaxi-safety.png", read_minutes=5,
         excerpt="NVIDIA Halos OS delivers safety-certified platform software, standardized "
                 "interfaces, AI guardrails and pre-deployment validation for L4 robotaxis.",
         body="NVIDIA Halos OS provides safety-certified platform software, standardized "
              "interfaces, AI guardrails, and pre-deployment validation for Level 4 robotaxi "
              "fleets. The approach builds safety into the autonomous-driving stack from the "
              "ground up rather than adding it after the fact."),
]

# --------------------------------------------------------------------------
# Driver downloads
# --------------------------------------------------------------------------
DRIVERS = [
    dict(product_series="GeForce RTX 50 Series", branch="Game Ready", version="566.36",
         os="Windows 11", released=date(2026, 6, 10), size_mb=712,
         highlights="Day-0 support for the latest AAA titles and DLSS 4 updates."),
    dict(product_series="GeForce RTX 50 Series", branch="Studio", version="566.14",
         os="Windows 11", released=date(2026, 5, 28), size_mb=705,
         highlights="Optimized and validated for creative applications."),
    dict(product_series="GeForce RTX 50 Series", branch="Game Ready", version="566.36",
         os="Windows 10", released=date(2026, 6, 10), size_mb=708,
         highlights="Day-0 support for the latest AAA titles and DLSS 4 updates."),
    dict(product_series="GeForce RTX 40 Series", branch="Game Ready", version="566.36",
         os="Windows 11", released=date(2026, 6, 10), size_mb=690,
         highlights="Performance optimizations for recent releases."),
    dict(product_series="GeForce RTX 40 Series", branch="Studio", version="566.14",
         os="Windows 11", released=date(2026, 5, 28), size_mb=688,
         highlights="Validated for content-creation workflows."),
    dict(product_series="GeForce RTX 40 Series", branch="Game Ready", version="565.90",
         os="Linux", released=date(2026, 4, 30), size_mb=395,
         highlights="Production branch for Linux gaming and Vulkan."),
    dict(product_series="GeForce RTX 30 Series", branch="Game Ready", version="566.36",
         os="Windows 11", released=date(2026, 6, 10), size_mb=672,
         highlights="Continued support for Ampere GeForce GPUs."),
    dict(product_series="RTX PRO / Workstation", branch="Studio", version="553.62",
         os="Windows 11", released=date(2026, 5, 15), size_mb=820,
         highlights="Enterprise-validated production branch (NVIDIA RTX Enterprise)."),
    dict(product_series="RTX PRO / Workstation", branch="Studio", version="553.24",
         os="Linux", released=date(2026, 3, 20), size_mb=430,
         highlights="Long-term support branch for professional Linux workstations."),
]

# --------------------------------------------------------------------------
# Benchmark users — alice.j@test.com et al. (password: TestPass123!)
# --------------------------------------------------------------------------
BENCHMARK_USERS = [
    dict(email="alice.j@test.com", name="Alice Johnson", password="TestPass123!",
         company="Pixel Forge Studios", country="United States", newsletter_opt_in=True),
    dict(email="bob.c@test.com", name="Bob Chen", password="TestPass123!",
         company="", country="United States", newsletter_opt_in=False),
    dict(email="carol.d@test.com", name="Carol Davis", password="TestPass123!",
         company="Helix Robotics", country="Canada", newsletter_opt_in=True),
    dict(email="david.k@test.com", name="David Kim", password="TestPass123!",
         company="", country="United Kingdom", newsletter_opt_in=False),
]

# --------------------------------------------------------------------------
# Notable reviews — placed on NON-task-target products to avoid answer leaks
# --------------------------------------------------------------------------
NOTABLE_REVIEWS = [
    dict(user_email="bob.c@test.com", product_slug="geforce-rtx-4090", rating=5,
         title="Still a monster", body="Two years on and the 4090 handles everything at 4K."),
    dict(user_email="carol.d@test.com", product_slug="jetson-agx-orin", rating=5,
         title="Perfect for our robots", body="64 GB lets us run large perception models at the edge."),
    dict(user_email="david.k@test.com", product_slug="geforce-rtx-4070-super", rating=4,
         title="Great 1440p value", body="Runs quiet and cool; DLSS 3 is excellent."),
    dict(user_email="bob.c@test.com", product_slug="shield-tv-pro", rating=5,
         title="Best streamer", body="The AI upscaling genuinely makes 1080p content look great."),
    dict(user_email="carol.d@test.com", product_slug="rtx-6000-ada", rating=5,
         title="Workstation beast", body="48 GB of ECC memory handles our largest scenes."),
]

# --------------------------------------------------------------------------
# Benchmark activity — pre-existing wishlists / orders (avoid task targets)
# --------------------------------------------------------------------------
BENCHMARK_ACTIVITY = [
    dict(user_email="alice.j@test.com",
         wishlist=["rtx-pro-6000-blackwell", "geforce-rtx-4080-super"],
         orders=[dict(products=["geforce-rtx-4090"], status="Delivered")]),
    dict(user_email="carol.d@test.com",
         wishlist=["jetson-orin-nx"],
         orders=[dict(products=["jetson-agx-orin"], status="Delivered")]),
]
