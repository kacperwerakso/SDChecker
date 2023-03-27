import platform
import psutil

def get_size(bytes, suffix="B"):
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f}{unit}{suffix}"
        bytes /= factor


print("-"*35, "Informacje o systemie ", "-"*35)
uname = platform.uname()
print(f"Nazwa systemu: {uname.system}")
print(f"Wydanie: {uname.release}")
print(f"Wersja: {uname.version}")
print(f"Wersja bitowa: {uname.machine}")



print("-"*34, "Informacje o procesorze ", "-"*34)
print(f"Procesor: {uname.processor}")
print("Ilość rdzeni:", psutil.cpu_count(logical=True))
cpufreq = psutil.cpu_freq()
print(f"Mhz: {cpufreq.current:.2f}")
print("Użycie procesora na poszczególne rdzenie:")
for i, percentage in enumerate(psutil.cpu_percent(percpu=True, interval=1)):
    print(f"Rdzeń {i}: {percentage}%")
print(f"Całkowite użycie procesora: {psutil.cpu_percent()}%")



print("-"*38, "Informacje o RAM", "-"*38)

svmem = psutil.virtual_memory()
print(f"Ilość RAM: {get_size(svmem.total)}")
print(f"Używane RAM: {get_size(svmem.used)}")



print("-"*36, "Informacje o dyskach", "-"*36)
print("Użycie dysków:")

partitions = psutil.disk_partitions()
for partition in partitions:
    print(f"- Dysk: {partition.device}")
    try:
        partition_usage = psutil.disk_usage(partition.mountpoint)
    except PermissionError:
        continue
    print(f"  Rozmiar: {get_size(partition_usage.total)}")
    print(f"  Użycie: {get_size(partition_usage.used)}")
    print(f"  Wolne miejsce: {get_size(partition_usage.free)}")



print("-"*37, "Informacje sieciowe", "-"*36)
if_addrs = psutil.net_if_addrs()
for interface_name, interface_addresses in if_addrs.items():
    for address in interface_addresses:
        if str(address.family) == 'AddressFamily.AF_INET':
            print(f"  Adres IP: {address.address}")
            print(f"  Maska podsieci: {address.netmask}")

input()