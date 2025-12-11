import platform
import psutil
import socket
import datetime
import argparse
import json
import getpass

try:
    import GPUtil
    HAVE_GPUTIL = True
except Exception:
    HAVE_GPUTIL = False

try:
    import cpuinfo
    HAVE_CPUINFO = True
except Exception:
    HAVE_CPUINFO = False

try:
    import distro
    HAVE_DISTRO = True
except Exception:
    HAVE_DISTRO = False

def get_size(bytes, suffix="B"):
    factor = 1024.0
    units = ["","K","M","G","T","P"]
    for unit in units:
        if abs(bytes) < factor:
            return f"{bytes:.2f}{unit}{suffix}"
        bytes /= factor
    return f"{bytes:.2f}E{suffix}"

def uptime_info():
    boot_ts = psutil.boot_time()
    boot = datetime.datetime.fromtimestamp(boot_ts)
    now = datetime.datetime.now()
    uptime = now - boot
    return {
        "boot_time": boot.isoformat(),
        "uptime_seconds": int(uptime.total_seconds()),
        "uptime_human": str(uptime).split('.')[0]
    }

def basic_system_info():
    uname = platform.uname()
    sys = {
        "system": uname.system,
        "node_name": uname.node,
        "release": uname.release,
        "version": uname.version,
        "machine": uname.machine,
        "processor": uname.processor or "unknown",
        "user": getpass.getuser()
    }
    if HAVE_DISTRO:
        sys["distro"] = distro.name(pretty=True)
    return sys

def cpu_info():
    info = {
        "physical_cores": psutil.cpu_count(logical=False),
        "total_logical_cpus": psutil.cpu_count(logical=True),
        "cpu_freq": None,
        "cpu_usage_per_core": None,
        "cpu_total_usage_percent": None,
        "detailed": None
    }
    try:
        cpufreq = psutil.cpu_freq()
        if cpufreq:
            info["cpu_freq"] = {
                "current_mhz": round(cpufreq.current, 2),
                "min_mhz": round(cpufreq.min, 2),
                "max_mhz": round(cpufreq.max, 2)
            }
    except Exception:
        pass

    info["cpu_usage_per_core"] = psutil.cpu_percent(interval=1, percpu=True)
    info["cpu_total_usage_percent"] = psutil.cpu_percent(interval=0.5)

    if HAVE_CPUINFO:
        try:
            ci = cpuinfo.get_cpu_info()
            info["detailed"] = {
                "brand_raw": ci.get("brand_raw"),
                "arch": ci.get("arch"),
                "bits": ci.get("bits"),
                "hz_advertised": ci.get("hz_advertised_friendly"),
                "hz_actual": ci.get("hz_actual_friendly"),
                "flags": ci.get("flags")
            }
        except Exception:
            pass
    return info

def memory_info():
    svmem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total": get_size(svmem.total),
        "available": get_size(svmem.available),
        "used": get_size(svmem.used),
        "percent": svmem.percent,
        "swap_total": get_size(swap.total),
        "swap_used": get_size(swap.used),
        "swap_percent": swap.percent
    }

def disks_info():
    parts = []
    for partition in psutil.disk_partitions(all=False):
        part = {
            "device": partition.device,
            "mountpoint": partition.mountpoint,
            "fstype": partition.fstype,
            "opts": partition.opts
        }
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            part["total"] = get_size(usage.total)
            part["used"] = get_size(usage.used)
            part["free"] = get_size(usage.free)
            part["percent"] = usage.percent
        except PermissionError:
            part["error"] = "PermissionError"
        parts.append(part)

    disk_io = psutil.disk_io_counters(perdisk=False)
    summary = {
        "partitions": parts,
        "io_total_read": get_size(disk_io.read_bytes) if disk_io else None,
        "io_total_write": get_size(disk_io.write_bytes) if disk_io else None,
        "io_counts_read": disk_io.read_count if disk_io else None,
        "io_counts_write": disk_io.write_count if disk_io else None
    }
    return summary

def network_info():
    info = {"interfaces": {}, "io_counters": None}
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    for ifname, addr_list in addrs.items():
        info["interfaces"][ifname] = []
        for addr in addr_list:
            entry = {
                "family": str(addr.family),
                "address": addr.address,
                "netmask": addr.netmask,
                "broadcast": addr.broadcast
            }
            info["interfaces"][ifname].append(entry)
    info["stats"] = {}
    for ifname, st in stats.items():
        info["stats"][ifname] = {
            "isup": st.isup,
            "duplex": str(st.duplex),
            "speed_mbps": st.speed,
            "mtu": st.mtu
        }
    io = psutil.net_io_counters(pernic=False)
    if io:
        info["io_counters"] = {
            "bytes_sent": get_size(io.bytes_sent),
            "bytes_recv": get_size(io.bytes_recv),
            "packets_sent": io.packets_sent,
            "packets_recv": io.packets_recv
        }
    return info

def gpu_info():
    if not HAVE_GPUTIL:
        return {"available": False, "note": "GPUtil not installed. Install with 'pip install GPUtil' for GPU info."}
    try:
        gpus = GPUtil.getGPUs()
        out = []
        for g in gpus:
            out.append({
                "id": g.id,
                "name": g.name,
                "load_percent": round(g.load * 100, 2),
                "memory_total": f"{g.memoryTotal}MB",
                "memory_used": f"{g.memoryUsed}MB",
                "memory_free": f"{g.memoryFree}MB",
                "memory_util_percent": round(g.memoryUtil * 100, 2),
                "temperature_c": getattr(g, "temperature", None)
            })
        return {"available": True, "gpus": out}
    except Exception as e:
        return {"available": False, "error": str(e)}

def sensors_info():
    out = {}
    try:
        temps = psutil.sensors_temperatures()
        out["temperatures"] = {k: [t._asdict() for t in v] for k, v in temps.items()} if temps else {}
    except Exception:
        out["temperatures_error"] = "not supported"

    try:
        fans = psutil.sensors_fans()
        out["fans"] = {k: [f._asdict() for f in v] for k, v in fans.items()} if fans else {}
    except Exception:
        out["fans_error"] = "not supported"

    try:
        batt = psutil.sensors_battery()
        if batt:
            out["battery"] = {
                "percent": batt.percent,
                "secsleft": batt.secsleft,
                "power_plugged": batt.power_plugged
            }
        else:
            out["battery"] = None
    except Exception:
        out["battery_error"] = "not supported"

    return out

def top_processes(n=5):
    procs = []
    for p in psutil.process_iter(attrs=['pid', 'name', 'username']):
        try:
            with p.oneshot():
                cpu = p.cpu_percent(interval=None)
                mem = p.memory_info().rss
                procs.append({
                    "pid": p.pid,
                    "name": p.info.get("name"),
                    "user": p.info.get("username"),
                    "cpu_percent": cpu,
                    "memory_rss": mem,
                    "memory_rss_human": get_size(mem)
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    by_cpu = sorted(procs, key=lambda x: x["cpu_percent"], reverse=True)[:n]
    by_mem = sorted(procs, key=lambda x: x["memory_rss"], reverse=True)[:n]
    return {"top_cpu": by_cpu, "top_memory": by_mem}

def running_services_and_connections():
    conns = []
    try:
        for c in psutil.net_connections(kind='inet'):
            if c.status == psutil.CONN_LISTEN:
                conns.append({
                    "fd": c.fd,
                    "family": str(c.family),
                    "type": str(c.type),
                    "laddr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None,
                    "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None,
                    "pid": c.pid
                })
    except Exception:
        pass
    return {"listening_sockets": conns}

def collect_all(args):
    report = {
        "generated_at": datetime.datetime.now().isoformat(),
        "basic_system": basic_system_info(),
        "uptime": uptime_info(),
        "cpu": cpu_info(),
        "memory": memory_info(),
        "disks": disks_info(),
        "network": network_info(),
        "sensors": sensors_info(),
        "gpu": gpu_info(),
        "processes": top_processes(n=args.top),
        "connections": running_services_and_connections()
    }
    return report

def get_primary_ipv4(network_report):
    for ifname, addrs in network_report["interfaces"].items():
        for a in addrs:
            if "AF_INET" in a["family"] and a["address"] and not a["address"].startswith("127."):
                return a["address"], ifname, network_report["stats"].get(ifname, {}).get("speed_mbps")
    try:
        h = socket.gethostbyname(socket.gethostname())
        if h and not h.startswith("127."):
            return h, "hostname", None
    except Exception:
        pass
    return None, None, None

def human_percent(x):
    try:
        return f"{float(x):.1f}%"
    except Exception:
        return str(x)

def pretty_print(report, show_boot=False):
    sys = report.get("basic_system", {})
    print()
    print("="*16, "Informacje systemowe", "="*16)
    print(f"{sys.get('system','-')} {sys.get('release','-')} ({sys.get('machine','-')}) - user: {sys.get('user','-')}")
    if sys.get("distro"):
        print("Distro:", sys["distro"])
    print()

    up = report.get("uptime", {})
    if show_boot:
        print("Czas pracy:", up.get("uptime_human","-"), "| Boot:", up.get("boot_time","-"))
    else:
        print("Czas pracy:", up.get("uptime_human","-"))
    print()

    print("-"*24, "CPU", "-"*25)
    cpu = report.get("cpu", {})
    phys = cpu.get("physical_cores") or cpu.get("total_logical_cpus") or "-"
    print(f"Ilość rdzeni: {phys}")
    if cpu.get("cpu_freq"):
        print("Częstotliwość (MHz):", cpu["cpu_freq"].get("current_mhz", "-"))
    total_cpu = cpu.get("cpu_total_usage_percent")
    try:
        total_cpu_f = float(total_cpu) if total_cpu is not None else 0.0
    except Exception:
        total_cpu_f = 0.0
    print("Użycie CPU (całość):", f"{total_cpu_f:.1f}%")
    if cpu.get("detailed") and cpu["detailed"].get("brand_raw"):
        print("CPU model:", cpu["detailed"]["brand_raw"])
    print()

    print("-"*23, "Pamięć", "-"*23)
    mem = report.get("memory", {})
    print("RAM całkowity:", mem.get("total", "-"))
    print("RAM użyte:", mem.get("used", "-"), f"({mem.get('percent','-')}%)")
    print()


    print("-"*23, "Dyski", "-"*24)
    for p in report.get("disks", {}).get("partitions", []):
        dev = p.get("device", "-")
        mount = p.get("mountpoint", "-")
        fstype = p.get("fstype") or "-"
        total = p.get("total", "-")
        pct = p.get("percent", "-")
        print(f"{dev} typ: {fstype}  rozmiar: {total}  zajęte: {pct}%")
    print()

    print("-" * 24, "Sieć", "-" * 24)
    network = report.get("network", {})
    interfaces = network.get("interfaces", {})

    primary_ipv4, primary_if, _ = get_primary_ipv4(network)
    if primary_ipv4:
        print(f"Adres IPv4: {primary_ipv4}")
    else:
        print("Adres IPv4: brak")

    primary_ipv6 = None
    for name, addrs in interfaces.items():
        primary_ipv6 = next(
            (a["address"] for a in addrs if "AF_INET6" in a["family"]),
            None
        )
        if primary_ipv6:
            break

    if primary_ipv6:
        print(f"Adres IPv6: {primary_ipv6}")

    vpn_active = any("VPN" in name.upper() for name in interfaces.keys())
    print("VPN: aktywny" if vpn_active else "VPN: brak")

    print()

    print("-" * 25, "GPU", "-" * 24)
    gpu = report.get("gpu", {})
    if gpu.get("available"):
        for g in gpu.get("gpus", []):
            mem_used = g.get("memory_used")
            mem_total = g.get("memory_total")
            mem_used_s = f"{mem_used}MB" if mem_used is not None else "-"
            mem_total_s = f"{mem_total}MB" if mem_total is not None else "-"
            load = g.get("load_percent") or 0.0
            temp = g.get("temperature_c") or "-"
            print(f"{g.get('name','-')}  | Obciążenie: {float(load):.1f}% \nPamięć VRAM: {mem_used_s} / {mem_total_s}  | Temp: {temp}C")
    else:
        print(gpu.get("note") or gpu.get("error") or "Brak info o GPU")
    print()
    print(54*"=")





def main():
    parser = argparse.ArgumentParser(description="Rozszerzone info o systemie")
    parser.add_argument("--json", action="store_true", help="zapisz raport do system_report.json")
    parser.add_argument("--top", type=int, default=5, help="ile top procesów pokazać")
    parser.add_argument("--quiet", action="store_true", help="tylko json (bez pretty print)")
    args = parser.parse_args()

    report = collect_all(args)

    if not args.quiet:
        pretty_print(report)

    if args.json:
        fname = "system_report.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print("Zapisano raport do", fname)

if __name__ == "__main__":
    main()
