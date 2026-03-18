#!/usr/bin/env python3
"""
ZetaView PDF Data Extractor and FCS Plotter

Extracts data from ZetaView PDF reports, reads corresponding FCS files,
and generates particle size distribution plots with median and SEM.

Usage:
    python app/zetaview_plotter.py
    python app/zetaview_plotter.py "<directory_path>"
"""

import argparse
import os
import sys
import re
import csv
import tempfile
from pathlib import Path
import PyPDF2
from collections import defaultdict
import statistics
import fcsparser
import pandas as pd
import numpy as np

_MPL_CACHE_DIR = Path(tempfile.gettempdir()) / "ntawesome-mpl-cache"
_MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(_MPL_CACHE_DIR))
os.environ.setdefault("XDG_CACHE_HOME", str(_MPL_CACHE_DIR))

import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats


def configure_console_output():
    """Use UTF-8 console streams on Windows so status messages do not crash cmd.exe."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue

        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def extract_pdf_text(pdf_path):
    """Extract text content from PDF file."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return None


def extract_values(text):
    """Extract the required values from PDF text."""
    if not text:
        return None
    
    values = {
        'median_x50': None,
        'original_concentration': None,
        'std_dev': None,
        'traced_particles': None,
        'positions_removed': 0,
        'dilution_factor': None,
        'conversion_factor': None
    }
    
    # Extract Median (X50)
    median_match = re.search(r'Median \(X50\)\s+([0-9.]+)', text)
    if median_match:
        values['median_x50'] = float(median_match.group(1))
    
    # Extract Original Concentration - handle PDF text extraction line breaks
    orig_conc_match = re.search(r'Original Concentration:\s+([0-9.E+]+)', text)
    if orig_conc_match:
        values['original_concentration'] = orig_conc_match.group(1)
    
    # Extract StdDev from X Values table - Number column
    stddev_match = re.search(r'StdDev\s+([0-9.]+)', text)
    if stddev_match:
        values['std_dev'] = float(stddev_match.group(1))
    
    # Extract Number of Traced Particles
    traced_match = re.search(r'Number of Traced Particles:\s+([0-9]+)', text)
    if traced_match:
        values['traced_particles'] = int(traced_match.group(1))
    
    # Extract Positions Removed (extract the number before "Positions Removed")
    positions_match = re.search(r'(\d+)\s+Positions?\s+Removed\s+for\s+Analysis', text)
    if positions_match:
        values['positions_removed'] = int(positions_match.group(1))
    else:
        values['positions_removed'] = 0
    
    # Extract Dilution Factor - handle numbers split by spaces in PDF extraction
    dilution_match = re.search(r'Dilution Factor:\s+([0-9]+(?:\s+[0-9]+)*)', text)
    if dilution_match:
        # Remove spaces from the captured dilution factor
        dilution_str = dilution_match.group(1).replace(' ', '')
        values['dilution_factor'] = int(dilution_str)
    
    return values


def get_base_name(filename):
    """Extract base name from filename by removing _000, _001, _002 endings."""
    base = filename.replace('.pdf', '')
    if base.endswith('_000') or base.endswith('_001') or base.endswith('_002'):
        return base[:-4]
    return base


def clean_sample_name(base_name):
    """Clean up sample name for display by removing date and technical prefixes."""
    clean_name = re.sub(r'^\d{8}_\d{4}_', '', base_name)
    clean_name = re.sub(r'_size_\d+(?=_|$)', '', clean_name)
    clean_name = re.sub(r'\s+', ' ', clean_name.replace('_', ' ')).strip()
    return clean_name


def make_output_stem(display_name):
    """Convert display names into Windows-safe output filenames."""
    safe_name = re.sub(r'[<>:"/\\|?*]+', '_', display_name.strip())
    safe_name = re.sub(r'\s+', '_', safe_name)
    return safe_name.strip('._') or "sample"


def normalize_input_path(raw_path):
    """Normalize pasted or dragged file/folder paths from macOS or Windows terminals."""
    if raw_path is None:
        return None

    path_str = str(raw_path).strip()
    if not path_str:
        return None

    path_str = path_str.strip('"\'')

    # On Windows, backslashes are path separators, not escape characters.
    # Preserve Windows and UNC paths exactly so folders like "\# Data" remain valid.
    if os.name == "nt" and "\\" in path_str:
        return Path(path_str).expanduser()

    # macOS terminals often paste escaped paths when files are dragged in.
    replacements = {
        '\\ ': ' ',
        '\\#': '#',
        '\\&': '&',
        '\\(': '(',
        '\\)': ')',
        '\\[': '[',
        '\\]': ']',
    }
    for old, new in replacements.items():
        path_str = path_str.replace(old, new)

    return Path(path_str).expanduser()


def resolve_input_directory(raw_path):
    """Resolve a user-supplied file or directory path into the folder to process."""
    path = normalize_input_path(raw_path)
    if path is None:
        return None, "❌ No path provided."

    try:
        if path.exists() and path.is_file():
            return path.parent, f"📄 File detected. Using parent directory: {path.parent}"

        if path.exists() and path.is_dir():
            return path, None
    except OSError as exc:
        return None, f"❌ Could not access path: {raw_path} ({exc})"

    return None, f"❌ Path not found: {raw_path}"


def find_matching_fcs(pdf_filename, fcs_files):
    """Find the corresponding FCS file for a PDF file."""
    pdf_base = pdf_filename.replace('.pdf', '')
    
    for fcs_file in fcs_files:
        if fcs_file.startswith(pdf_base):
            return fcs_file
    return None


def find_matching_txt(pdf_filename, txt_files):
    """Find the corresponding TXT file for a PDF file."""
    pdf_base = pdf_filename.replace('.pdf', '')
    
    for txt_file in txt_files:
        if txt_file.startswith(pdf_base):
            return txt_file
    return None


def load_fcs_data(fcs_path):
    """Load particle size data from FCS file."""
    try:
        meta, data = fcsparser.parse(fcs_path, reformat_meta=True)
        # Extract particle sizes (assuming 'Size' column contains diameter in nm)
        sizes = data['Size'].values
        # Filter out any invalid values
        sizes = sizes[sizes > 0]
        return sizes
    except Exception as e:
        print(f"Error reading FCS file {fcs_path}: {e}")
        return None


def get_conversion_factor_from_txt(txt_path):
    """Get the base conversion factor (particles/ml per raw count) from TXT file."""
    try:
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as file:
            lines = file.readlines()
        
        # Find the start of the size distribution data
        data_start = -1
        for i, line in enumerate(lines):
            if 'Size / nm\tNumber\tConcentration / cm-3' in line:
                data_start = i + 1
                break
        
        if data_start == -1:
            return None
        
        conversion_factors = []
        
        # Parse the data lines to find conversion factor
        for line in lines[data_start:]:
            line = line.strip()
            if not line:
                break
            
            try:
                parts = line.split('\t')
                if len(parts) >= 3:
                    number = float(parts[1])  # Raw particle count
                    concentration_cm3 = float(parts[2])  # particles/cm³
                    
                    if number > 0 and concentration_cm3 > 0:  # Valid data
                        # This gives us particles/cm³ per raw count (before dilution)
                        conversion_factor = concentration_cm3 / number
                        conversion_factors.append(conversion_factor)
            except (ValueError, IndexError):
                continue
        
        if conversion_factors:
            # Return the most common conversion factor (should be consistent)
            return np.median(conversion_factors)
        else:
            return None
        
    except Exception as e:
        print(f"Error reading TXT file {txt_path}: {e}")
        return None


def group_replicates(csv_data):
    """Group data by base filename and identify complete replicate sets."""
    groups = defaultdict(list)
    
    for data in csv_data:
        base_name = get_base_name(data['filename'])
        groups[base_name].append(data)
    
    complete_groups = {}
    incomplete_files = []
    
    for base_name, files in groups.items():
        if len(files) == 3:
            suffixes = set()
            for file_data in files:
                filename = file_data['filename'].replace('.pdf', '')
                if filename.endswith('_000'):
                    suffixes.add('000')
                elif filename.endswith('_001'):
                    suffixes.add('001')
                elif filename.endswith('_002'):
                    suffixes.add('002')
            
            if suffixes == {'000', '001', '002'}:
                complete_groups[base_name] = files
            else:
                incomplete_files.extend(files)
        else:
            incomplete_files.extend(files)
    
    return complete_groups, incomplete_files


def calculate_averages(group_data):
    """Calculate averages for a group of replicates."""
    median_values = [d['median_x50'] for d in group_data if d['median_x50'] is not None]
    std_dev_values = [d['std_dev'] for d in group_data if d['std_dev'] is not None]
    traced_particles_values = [d['traced_particles'] for d in group_data if d['traced_particles'] is not None]
    positions_removed_values = [d['positions_removed'] for d in group_data if d['positions_removed'] is not None]
    dilution_factor_values = [d['dilution_factor'] for d in group_data if d['dilution_factor'] is not None]
    conversion_factor_values = [d['conversion_factor'] for d in group_data if d['conversion_factor'] is not None]
    
    concentration_values = []
    for d in group_data:
        if d['original_concentration'] is not None:
            try:
                concentration_values.append(float(d['original_concentration']))
            except ValueError:
                pass
    
    averages = {
        'median_x50': statistics.mean(median_values) if median_values else None,
        'original_concentration': f"{statistics.mean(concentration_values):.2E}" if concentration_values else None,
        'std_dev': statistics.mean(std_dev_values) if std_dev_values else None,
        'traced_particles': round(statistics.mean(traced_particles_values)) if traced_particles_values else None,
        'positions_removed': round(statistics.mean(positions_removed_values)) if positions_removed_values else 0,
        'dilution_factor': round(statistics.mean(dilution_factor_values)) if dilution_factor_values else None,
        'conversion_factor': f"{statistics.mean(conversion_factor_values):.2E}" if conversion_factor_values else None
    }
    
    return averages


def extract_histogram_data(complete_groups, directory):
    """Extract histogram data (particles/ml) using FCS files with conversion from TXT files."""
    # Find all FCS and TXT files
    fcs_files = list(directory.glob("*.fcs"))
    fcs_filenames = [f.name for f in fcs_files]
    txt_files = list(directory.glob("*.txt"))
    txt_filenames = [f.name for f in txt_files]
    
    # Define the same log-spaced bins used in plotting (10 to 2000 nm, 50 bins)
    log_bins = np.logspace(np.log10(10), np.log10(2000), 50)
    bin_centers = (log_bins[:-1] + log_bins[1:]) / 2
    
    histogram_data = {}
    
    for base_name, group_data in sorted(complete_groups.items()):
        print(f"Extracting histogram data for: {base_name}")
        
        sample_histograms = []
        replicate_names = []
        
        # Sort files to ensure consistent ordering (000, 001, 002)
        sorted_group = sorted(group_data, key=lambda x: x['filename'] if isinstance(x, dict) else x)
        
        for file_data in sorted_group:
            pdf_filename = file_data['filename'] if isinstance(file_data, dict) else file_data
            fcs_filename = find_matching_fcs(pdf_filename, fcs_filenames)
            txt_filename = find_matching_txt(pdf_filename, txt_filenames)
            
            if fcs_filename and txt_filename:
                # Load FCS data (raw particle sizes)
                fcs_path = directory / fcs_filename
                sizes = load_fcs_data(fcs_path)
                
                # Get conversion factor from TXT file
                txt_path = directory / txt_filename
                base_conversion_factor = get_conversion_factor_from_txt(txt_path)
                
                # Get dilution factor from file_data (extracted from PDF)
                dilution_factor = file_data.get('dilution_factor', 1) if isinstance(file_data, dict) else 1
                
                if sizes is not None and base_conversion_factor is not None:
                    # Filter sizes to our range of interest (10-2000 nm)
                    sizes_filtered = sizes[(sizes >= 10) & (sizes <= 2000)]
                    
                    # Generate histogram counts from FCS data
                    counts, _ = np.histogram(sizes_filtered, bins=log_bins)
                    
                    # Convert raw counts to particles/ml using conversion factor and dilution
                    # counts × (particles/cm³ per count) × dilution_factor = particles/ml
                    bin_concentrations = counts * base_conversion_factor * dilution_factor
                    
                    sample_histograms.append(bin_concentrations)
                    
                    # Create replicate name from filename
                    replicate_suffix = pdf_filename.replace('.pdf', '')[-4:]  # Get _000, _001, _002
                    replicate_names.append(f"{base_name}{replicate_suffix}")
                    
                    print(f"  ✅ Processed {pdf_filename}: conversion={base_conversion_factor:.2E}, dilution={dilution_factor}")
                else:
                    print(f"  Warning: Could not process {pdf_filename} - missing data")
            else:
                missing = []
                if not fcs_filename:
                    missing.append("FCS")
                if not txt_filename:
                    missing.append("TXT")
                print(f"  Warning: Could not find matching {'/'.join(missing)} file(s) for {pdf_filename}")
        
        if len(sample_histograms) == 3:  # Complete set
            histogram_data[base_name] = {
                'bin_centers': bin_centers,
                'replicates': sample_histograms,
                'replicate_names': replicate_names
            }
        else:
            print(f"  Warning: Incomplete data for {base_name}, skipping")
    
    return histogram_data


def export_histogram_data_to_csv(histogram_data, output_dir):
    """Export raw histogram data to CSV with replicates side by side per sample."""
    if not histogram_data:
        print("No histogram data to export")
        return
    
    # Get bin centers (same for all samples)
    first_sample = next(iter(histogram_data.values()))
    bin_centers = first_sample['bin_centers']
    
    # Create CSV filename
    csv_filename = output_dir / "histogram_raw_data.csv"
    
    print(f"📊 Exporting raw histogram data to: {csv_filename.name}")
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Create headers
        headers = ['Diameter_nm']
        
        # Sort samples alphabetically for consistent output
        sorted_samples = sorted(histogram_data.keys())
        
        for sample_name in sorted_samples:
            clean_name = clean_sample_name(sample_name)
            # Add three columns for each sample (one per replicate)
            headers.extend([
                f"{clean_name}_rep1",
                f"{clean_name}_rep2", 
                f"{clean_name}_rep3"
            ])
        
        writer.writerow(headers)
        
        # Write data rows
        for i, diameter in enumerate(bin_centers):
            row = [f"{diameter:.2f}"]  # Diameter with 2 decimal places
            
            for sample_name in sorted_samples:
                sample_data = histogram_data[sample_name]
                replicates = sample_data['replicates']
                
                # Add concentrations from all 3 replicates for this bin
                for replicate_counts in replicates:
                    row.append(f"{replicate_counts[i]:.2E}")  # Scientific notation for concentrations
            
            writer.writerow(row)
        
        # Add metadata section
        writer.writerow([])
        writer.writerow(['=== METADATA ==='])
        writer.writerow(['Description', 'Concentration histogram data from ZetaView particle size analysis (particles/ml with dilution factor applied)'])
        writer.writerow(['Units', 'particles/ml'])
        writer.writerow(['Bin count', len(bin_centers)])
        writer.writerow(['Diameter range', f"{bin_centers[0]:.2f} - {bin_centers[-1]:.2f} nm"])
        writer.writerow(['Bin spacing', 'Log-spaced'])
        writer.writerow(['Samples processed', len(sorted_samples)])
        writer.writerow(['Replicates per sample', '3'])
        
        # List all samples
        writer.writerow([])
        writer.writerow(['Sample names:'])
        for sample_name in sorted_samples:
            clean_name = clean_sample_name(sample_name)
            writer.writerow([clean_name])
    
    print(f"   ✅ Raw histogram data exported: {len(sorted_samples)} samples × 3 replicates")
    return csv_filename


def create_size_distribution_plots(complete_groups, directory, averaged_data):
    """Create a single summary plot with all samples as subplots using FCS data with TXT conversion."""
    # Find all FCS and TXT files
    fcs_files = list(directory.glob("*.fcs"))
    fcs_filenames = [f.name for f in fcs_files]
    txt_files = list(directory.glob("*.txt"))
    txt_filenames = [f.name for f in txt_files]
    
    print(f"\nCreating particle size distribution summary plot...")
    
    # Set up plot style with Arial font
    plt.style.use('default')
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
    plt.rcParams['font.weight'] = 'normal'
    sns.set_palette("husl")
    
    # Use fixed 4x4 grid
    n_samples = len(complete_groups)
    n_cols = 4
    n_rows = (n_samples + n_cols - 1) // n_cols  # Ceiling division for dynamic rows
    
    print(f"Creating {n_rows}x{n_cols} grid for {n_samples} samples")
    
    # Convert 3x3 cm to inches (1 inch = 2.54 cm)
    subplot_size_inches = 3 / 2.54
    
    # Create figure with subplots (3x3 cm each)
    fig, axes = plt.subplots(n_rows, n_cols, 
                            figsize=(n_cols * subplot_size_inches, n_rows * subplot_size_inches),
                            squeeze=False)
    
    # Create dictionary for easy lookup of averaged data
    avg_data_dict = {data['sample_name']: data for data in averaged_data}
    
    plots_created = 0
    
    for idx, (base_name, group_data) in enumerate(sorted(complete_groups.items())):
        row = idx // n_cols
        col = idx % n_cols
        ax = axes[row, col]
        
        print(f"Processing subplot {idx+1}/{n_samples}: {base_name}")
        
        # Collect size data from all 3 replicates using FCS files with TXT conversion
        replicate_histograms = []
        
        for file_data in group_data:
            pdf_filename = file_data['filename']
            fcs_filename = find_matching_fcs(pdf_filename, fcs_filenames)
            txt_filename = find_matching_txt(pdf_filename, txt_filenames)
            
            if fcs_filename and txt_filename:
                # Load FCS data (raw particle sizes)
                fcs_path = directory / fcs_filename
                sizes = load_fcs_data(fcs_path)
                
                # Get conversion factor from TXT file
                txt_path = directory / txt_filename
                base_conversion_factor = get_conversion_factor_from_txt(txt_path)
                
                # Get dilution factor from file_data (extracted from PDF)
                dilution_factor = file_data.get('dilution_factor', 1)
                
                if sizes is not None and base_conversion_factor is not None:
                    # Filter sizes to our range of interest (10-2000 nm)
                    sizes_filtered = sizes[(sizes >= 10) & (sizes <= 2000)]
                    
                    # Generate histogram counts from FCS data
                    log_bins = np.logspace(np.log10(10), np.log10(2000), 50)
                    counts, _ = np.histogram(sizes_filtered, bins=log_bins)
                    
                    # Convert raw counts to particles/ml
                    bin_concentrations = counts * base_conversion_factor * dilution_factor
                    
                    replicate_histograms.append(bin_concentrations)
                else:
                    print(f"  Warning: Could not process {pdf_filename}")
            else:
                print(f"  Warning: Could not find matching files for {pdf_filename}")
        
        if len(replicate_histograms) < 3:
            print(f"  Skipping {base_name}: insufficient data")
            ax.text(0.5, 0.5, 'No Data', ha='center', va='center', transform=ax.transAxes)
            ax.set_xlim(10, 2000)
            ax.set_xscale('log')
            continue
        
        # Define log-spaced bins from 10 to 2000 nm
        log_bins = np.logspace(np.log10(10), np.log10(2000), 50)  # Same bins as individual plots
        bin_centers = (log_bins[:-1] + log_bins[1:]) / 2
        
        # Prepare histogram data for median calculation
        histogram_data = []
        for bin_concentrations in replicate_histograms:
            histogram_data.append((bin_centers, bin_concentrations))
        
        # Calculate median and SEM across replicates
        if len(histogram_data) == 3:
            # Align all histograms to the same bins
            bin_centers = histogram_data[0][0]  # Use the same bins for all
            all_counts = np.array([data[1] for data in histogram_data])
            
            # Calculate median and SD
            median_counts = np.median(all_counts, axis=0)
            sd_counts = np.std(all_counts, axis=0, ddof=1)
            
            # Plot median line (thinner, darker)
            ax.plot(bin_centers, median_counts, color='darkblue', linewidth=0.6, zorder=10)
            
            # Add SD shading (visible blue, fully filled)
            ax.fill_between(bin_centers, 
                          median_counts - sd_counts, 
                          median_counts + sd_counts,
                          alpha=0.6, color='cornflowerblue', zorder=5, 
                          linewidth=0, edgecolor='none')
        
        # Format the plot
        ax.set_xscale('log')
        ax.set_xlim(10, 2000)
        
        # Create a clean title with smart line wrapping for long titles
        clean_title = clean_sample_name(base_name)
        
        # Split long titles into 2 or 3 lines with smarter logic
        words = clean_title.split()
        
        if len(clean_title) > 35 and len(words) >= 6:  # Very long titles get 3 lines
            # Split into 3 roughly equal parts
            third = len(words) // 3
            line1 = ' '.join(words[:third])
            line2 = ' '.join(words[third:third*2])
            line3 = ' '.join(words[third*2:])
            title_text = f"{line1}\n{line2}\n{line3}"
        elif len(clean_title) > 20:  # Medium titles get 2 lines
            # Try to split at logical break points first
            best_split = len(words) // 2
            
            # Look for good break points (like "size", "25x", numbers)
            for i, word in enumerate(words[:-1]):  # Don't split on last word
                if word in ['size', '25x', 'VLP'] or any(c.isdigit() for c in word):
                    if abs(i + 1 - len(words) // 2) <= 2:  # Within 2 words of midpoint
                        best_split = i + 1
                        break
            
            line1 = ' '.join(words[:best_split])
            line2 = ' '.join(words[best_split:])
            title_text = f"{line1}\n{line2}"
        else:
            title_text = clean_title
            
        ax.set_title(title_text, fontsize=4.5, fontweight='normal', pad=3)
        
        # Add grid
        ax.grid(True, alpha=0.2, linestyle='-', linewidth=0.3)
        ax.set_axisbelow(True)
        
        # Set custom x-axis ticks and labels (linear values on log scale)
        ax.set_xticks([10, 100, 1000])
        ax.set_xticklabels(['10', '100', '1000'])
        
        # Format axes with readable font size, thinner lines, and shorter ticks
        ax.tick_params(axis='both', which='major', labelsize=4, width=0.3, length=2, pad=1)
        ax.tick_params(axis='both', which='minor', labelsize=3, width=0.2, length=1)
        
        # Fix the scientific notation formatting on y-axis to be smaller and moved left
        ax.yaxis.get_offset_text().set_fontsize(4)
        ax.ticklabel_format(style='scientific', axis='y', scilimits=(0,0), useMathText=True)
        ax.yaxis.get_offset_text().set_fontsize(4)
        # Move the scientific notation offset text above the y-axis labels
        ax.yaxis.get_offset_text().set_horizontalalignment('center')
        ax.yaxis.get_offset_text().set_position((-0.05, 1))
        
        # Make spine lines thinner
        for spine in ax.spines.values():
            spine.set_linewidth(0.3)
        
        # Set reasonable y-limits
        if len(replicate_histograms) > 0:
            max_count = max([max(data[1]) for data in histogram_data])
            ax.set_ylim(0, max_count * 1.1)
        
        # Add inset with PDF-extracted values
        if base_name in avg_data_dict:
            avg_data = avg_data_dict[base_name]
            median_diameter = avg_data['median_x50']
            concentration = avg_data['original_concentration']
            
            # Create text box with key values (simplified format)
            info_text = f"{median_diameter:.1f} nm diameter\n"
            if concentration:
                # Format concentration in scientific notation
                conc_val = float(concentration)
                info_text += f"{conc_val:.1E} particles/mL"
            
            # Add text box in upper right (same font size as axis labels)
            ax.text(0.98, 0.98, info_text, 
                   transform=ax.transAxes, 
                   fontsize=3, 
                   verticalalignment='top',
                   horizontalalignment='right',
                   bbox=dict(boxstyle='round,pad=0.15', 
                           facecolor='white', 
                           alpha=0.8,
                           edgecolor='gray',
                           linewidth=0.3))
        
        plots_created += 1
    
    # Hide empty subplots
    for idx in range(n_samples, n_rows * n_cols):
        row = idx // n_cols
        col = idx % n_cols
        axes[row, col].set_visible(False)
    
    # Add common labels
    fig.text(0.5, 0.02, 'Diameter (nm)', ha='center', fontsize=6, fontweight='normal')
    fig.text(0.02, 0.5, 'Particles/mL', va='center', rotation='vertical', fontsize=6, fontweight='normal')
    
    # Add main title
    fig.suptitle('Particle Size Distribution Summary', fontsize=8, fontweight='normal', y=0.98)
    
    # Adjust layout with increased spacing for titles
    plt.tight_layout()
    plt.subplots_adjust(left=0.08, bottom=0.08, top=0.92, hspace=0.6, wspace=0.4)
    
    # Create output directory
    output_dir = directory / "NTAwesome Output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the plot as PDF (vector format)
    plot_filename = output_dir / "particle_distribution_summary.pdf"
    plt.savefig(plot_filename, format='pdf', bbox_inches='tight')
    plt.close()
    
    print(f"Summary plot saved: {plot_filename.name}")
    print(f"Created {plots_created} subplots in summary")
    return 1  # Return 1 since we created 1 summary plot


def process_directory_automatic(directory, complete_groups):
    """Automatic directory processing without user interaction."""
    print(f"📁 Processing directory: {directory}")
    
    # Find all FCS and TXT files
    fcs_files = list(directory.glob("*.fcs"))
    fcs_filenames = [f.name for f in fcs_files]
    txt_files = list(directory.glob("*.txt"))
    txt_filenames = [f.name for f in txt_files]
    
    # Convert complete_groups format for compatibility
    csv_data = []
    groups_for_processing = {}
    
    # Extract data from PDFs (only for complete groups)
    for base_name, filenames in complete_groups.items():
        group_data = []
        
        for filename in filenames:
            pdf_path = directory / filename
            print(f"📄 Processing: {filename}")
            
            # Ensure file exists and is accessible
            if not pdf_path.exists():
                print(f"  ⚠️  Warning: File not found: {pdf_path}")
                continue
                
            if not pdf_path.is_file():
                print(f"  ⚠️  Warning: Not a file: {pdf_path}")
                continue
            
            try:
                text = extract_pdf_text(pdf_path)
                if text is None:
                    print(f"  ⚠️  Warning: Could not extract text from {filename}")
                    continue
                    
                values = extract_values(text)
                
                if values:
                    # Find matching FCS and TXT files
                    matching_fcs = find_matching_fcs(filename, fcs_filenames)
                    matching_txt = find_matching_txt(filename, txt_filenames)
                    
                    # Get conversion factor from TXT file
                    conversion_factor = None
                    if matching_txt:
                        txt_path = directory / matching_txt
                        conversion_factor = get_conversion_factor_from_txt(txt_path)
                    
                    file_data = {
                        'filename': filename,
                        'fcs_file': matching_fcs if matching_fcs else 'Not found',
                        'txt_file': matching_txt if matching_txt else 'Not found',
                        'median_x50': values['median_x50'],
                        'original_concentration': values['original_concentration'],
                        'std_dev': values['std_dev'],
                        'traced_particles': values['traced_particles'],
                        'positions_removed': values['positions_removed'],
                        'dilution_factor': values['dilution_factor'],
                        'conversion_factor': conversion_factor
                    }
                    csv_data.append(file_data)
                    group_data.append(file_data)
                    print(f"  ✅ Successfully extracted data from {filename}")
                else:
                    print(f"  ⚠️  Warning: Could not extract values from {filename}")
            except Exception as e:
                print(f"  ❌ Error processing {filename}: {e}")
        
        if group_data:
            groups_for_processing[base_name] = group_data
        else:
            print(f"  ❌ No data extracted for group: {base_name}")
    
    # Calculate averages
    averaged_data = []
    for base_name, group_data in groups_for_processing.items():
        averages = calculate_averages(group_data)
        averaged_data.append({
            'sample_name': base_name,
            'median_x50': averages['median_x50'],
            'original_concentration': averages['original_concentration'],
            'std_dev': averages['std_dev'],
            'traced_particles': averages['traced_particles'],
            'positions_removed': averages['positions_removed'],
            'dilution_factor': averages['dilution_factor'],
            'conversion_factor': averages['conversion_factor']
        })
    
    # Create output directory
    output_dir = directory / "NTAwesome Output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write CSV
    output_file = output_dir / "zetaview_data_with_averages.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        writer.writerow(['=== Individual Measurements ==='])
        fieldnames1 = ['filename', 'fcs_file', 'txt_file', 'median_x50', 'original_concentration', 'std_dev', 'traced_particles', 'positions_removed', 'dilution_factor', 'conversion_factor']
        writer.writerow(fieldnames1)
        
        for data in csv_data:
            writer.writerow([data['filename'], data['fcs_file'], data.get('txt_file', 'Not found'), data['median_x50'], data['original_concentration'], 
                           data['std_dev'], data['traced_particles'], data['positions_removed'], data['dilution_factor'], data.get('conversion_factor', 'N/A')])
        
        writer.writerow([])
        writer.writerow(['=== Replicates Averaged ==='])
        fieldnames2 = ['sample_name', 'median_x50', 'original_concentration', 'std_dev', 'traced_particles', 'positions_removed', 'dilution_factor', 'conversion_factor']
        writer.writerow(fieldnames2)
        
        for data in averaged_data:
            writer.writerow([data['sample_name'], data['median_x50'], data['original_concentration'], 
                           data['std_dev'], data['traced_particles'], data['positions_removed'], data['dilution_factor'], data['conversion_factor']])
    
    # Extract and export raw histogram data
    print(f"\n📊 Extracting raw histogram data...")
    histogram_data = extract_histogram_data(groups_for_processing, directory)
    if histogram_data:
        export_histogram_data_to_csv(histogram_data, output_dir)
    
    # Create both summary and individual plots
    plots_created = 0
    
    print(f"\n📊 Creating summary plot...")
    summary_plots_created = create_size_distribution_plots(groups_for_processing, directory, averaged_data)
    plots_created += summary_plots_created
    
    print(f"\n📈 Creating individual plots...")
    individual_plots_created = create_individual_plots(groups_for_processing, directory, averaged_data)
    plots_created += individual_plots_created
    
    # Report final statistics
    print(f"\n✅ PROCESSING COMPLETE!")
    print("="*40)
    print(f"📊 Total PDF files processed: {len(csv_data)}")
    print(f"📈 Complete datasets: {len(groups_for_processing)}")
    print(f"📋 CSV data file: {output_file.name}")
    print(f"📋 Raw histogram data: histogram_raw_data.csv")
    print(f"📉 Plots created: {plots_created}")
    print("   - Summary plot: particle_distribution_summary.pdf")
    print(f"   - Individual plots: {individual_plots_created} files")
    print("\n🎉 All done! Files saved to the same directory.")


def process_directory(directory_path):
    """Process all PDF files in the given directory."""
    directory = Path(directory_path)
    
    if not directory.exists():
        print(f"Directory does not exist: {directory_path}")
        return
    
    # Find all PDF, FCS, and TXT files
    pdf_files = list(directory.glob("*.pdf"))
    fcs_files = list(directory.glob("*.fcs"))
    fcs_filenames = [f.name for f in fcs_files]
    txt_files = list(directory.glob("*.txt"))
    txt_filenames = [f.name for f in txt_files]
    
    if not pdf_files:
        print(f"No PDF files found in: {directory_path}")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process...")
    
    # Extract data from PDFs
    csv_data = []
    
    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name}")
        
        text = extract_pdf_text(pdf_file)
        values = extract_values(text)
        
        if values:
            # Find matching FCS and TXT files
            matching_fcs = find_matching_fcs(pdf_file.name, fcs_filenames)
            matching_txt = find_matching_txt(pdf_file.name, txt_filenames)
            
            # Get conversion factor from TXT file
            conversion_factor = None
            if matching_txt:
                txt_path = directory / matching_txt
                conversion_factor = get_conversion_factor_from_txt(txt_path)
            
            csv_data.append({
                'filename': pdf_file.name,
                'fcs_file': matching_fcs if matching_fcs else 'Not found',
                'txt_file': matching_txt if matching_txt else 'Not found',
                'median_x50': values['median_x50'],
                'original_concentration': values['original_concentration'],
                'std_dev': values['std_dev'],
                'traced_particles': values['traced_particles'],
                'positions_removed': values['positions_removed'],
                'dilution_factor': values['dilution_factor'],
                'conversion_factor': conversion_factor
            })
        else:
            print(f"  Warning: Could not extract data from {pdf_file.name}")
    
    # Group replicates and calculate averages
    complete_groups, incomplete_files = group_replicates(csv_data)
    
    # Calculate averages for complete groups
    averaged_data = []
    for base_name, group_data in complete_groups.items():
        averages = calculate_averages(group_data)
        averaged_data.append({
            'sample_name': base_name,
            'median_x50': averages['median_x50'],
            'original_concentration': averages['original_concentration'],
            'std_dev': averages['std_dev'],
            'traced_particles': averages['traced_particles'],
            'positions_removed': averages['positions_removed'],
            'dilution_factor': averages['dilution_factor'],
            'conversion_factor': averages['conversion_factor']
        })
    
    # Create output directory
    output_dir = directory / "NTAwesome Output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write to CSV
    output_file = output_dir / "zetaview_data_with_averages.csv"
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        writer.writerow(['=== Individual Measurements ==='])
        fieldnames1 = ['filename', 'fcs_file', 'txt_file', 'median_x50', 'original_concentration', 'std_dev', 'traced_particles', 'positions_removed', 'dilution_factor', 'conversion_factor']
        writer.writerow(fieldnames1)
        
        for data in csv_data:
            writer.writerow([data['filename'], data['fcs_file'], data.get('txt_file', 'Not found'), data['median_x50'], data['original_concentration'], 
                           data['std_dev'], data['traced_particles'], data['positions_removed'], data['dilution_factor'], data.get('conversion_factor', 'N/A')])
        
        writer.writerow([])
        writer.writerow(['=== Replicates Averaged ==='])
        fieldnames2 = ['sample_name', 'median_x50', 'original_concentration', 'std_dev', 'traced_particles', 'positions_removed', 'dilution_factor', 'conversion_factor']
        writer.writerow(fieldnames2)
        
        for data in averaged_data:
            writer.writerow([data['sample_name'], data['median_x50'], data['original_concentration'], 
                           data['std_dev'], data['traced_particles'], data['positions_removed'], data['dilution_factor'], data['conversion_factor']])
    
    # Extract and export raw histogram data
    print(f"\nExtracting raw histogram data...")
    histogram_data = extract_histogram_data(complete_groups, directory)
    if histogram_data:
        export_histogram_data_to_csv(histogram_data, output_dir)
    
    # Create plots
    plots_created = create_size_distribution_plots(complete_groups, directory, averaged_data)
    
    # Report statistics
    print(f"\n=== PROCESSING SUMMARY ===")
    print(f"Total PDF files processed: {len(csv_data)}")
    print(f"Complete replicate sets (3 files each): {len(complete_groups)}")
    print(f"Files in complete sets: {len(complete_groups) * 3}")
    print(f"Files not used (incomplete sets): {len(incomplete_files)}")
    print(f"Particle size distribution plots created: {plots_created}")
    
    if incomplete_files:
        print(f"\nFiles not used in averaging:")
        for file_data in incomplete_files:
            print(f"  - {file_data['filename']}")
    
    print(f"\nComplete sample names with 3 replicates each:")
    for base_name in sorted(complete_groups.keys()):
        print(f"  - {base_name}")
    
    print(f"\nData extracted and saved to: {output_file}")
    print(f"Individual measurements: {len(csv_data)} files")
    print(f"Averaged replicates: {len(averaged_data)} samples")


def show_splash_screen():
    """Display ASCII art splash screen and welcome message."""
    print("\n" + "="*70)
    print("""

   \  | __ __|   \                                                
    \ |    |    _ \ \ \  \   /  _ \   __|   _ \   __ `__ \    _ \ 
  |\  |    |   ___ \ \ \  \ /   __/ \__ \  (   |  |   |   |   __/ 
 _| \_|   _| _/    _\ \_/\_/  \___| ____/ \___/  _|  _|  _| \___| 
                                                                                                                                                                                         
    """)
    print("    ZetaView Nanoparticle Tracking Analysis - Data Processor")
    print("    Version 1.0 - Automated PDF & FCS Analysis")
    print()
    print("    Designed by R. Groß, Institute of Molecular Virology,")
    print("    Ulm University Hospital and Claude AI")
    print("    Questions? Contact me at ruediger.gross@uni-ulm.de")
    print("="*70 + "\n")


def get_directory_input():
    """Get directory path from user input."""
    print("📁 Please drag a PDF file or folder containing your ZetaView files into this terminal")
    print("   and press Enter, or type the path manually:")
    print()
    
    while True:
        user_input = input("Directory path: ").strip()
        
        directory, status_message = resolve_input_directory(user_input)
        if status_message:
            print(status_message)

        if directory is None:
            print("Please try again or check the path.")
            print("💡 Tip: Make sure the network drive is properly mounted")
            continue
        
        # Additional check for network drives
        if directory.exists():
            return directory
        else:
            print(f"❌ Directory not accessible: {directory}")
            print("Please try again or check the path.")
            print("💡 Tip: Make sure the network drive is properly mounted")


def analyze_datasets(directory):
    """Analyze directory and show what datasets are available."""
    print(f"\n🔍 Analyzing directory: {directory}")
    print("="*50)
    
    # Find all PDF files
    pdf_files = list(directory.glob("*.pdf"))
    
    if not pdf_files:
        print("❌ No PDF files found in this directory!")
        return None, None
    
    print(f"📄 Found {len(pdf_files)} PDF files")
    
    # Quick analysis to find complete groups
    groups = defaultdict(list)
    
    for pdf_file in pdf_files:
        # Skip our own output files
        if 'particle_distribution' in pdf_file.name:
            continue
            
        base_name = get_base_name(pdf_file.name)
        groups[base_name].append(pdf_file.name)
    
    # Find complete and incomplete groups
    complete_groups = {}
    incomplete_groups = {}
    
    for base_name, files in groups.items():
        if len(files) == 3:
            # Check if we have exactly 000, 001, 002
            suffixes = set()
            for filename in files:
                name_no_ext = filename.replace('.pdf', '')
                if name_no_ext.endswith('_000'):
                    suffixes.add('000')
                elif name_no_ext.endswith('_001'):
                    suffixes.add('001')
                elif name_no_ext.endswith('_002'):
                    suffixes.add('002')
            
            if suffixes == {'000', '001', '002'}:
                complete_groups[base_name] = files
            else:
                incomplete_groups[base_name] = files
        else:
            incomplete_groups[base_name] = files
    
    # Display results
    print(f"\n✅ Complete datasets (3 replicates each): {len(complete_groups)}")
    if complete_groups:
        for i, base_name in enumerate(sorted(complete_groups.keys()), 1):
            clean_name = clean_sample_name(base_name)
            print(f"   {i:2d}. {clean_name}")

    if incomplete_groups:
        print(f"\n⚠️  Incomplete datasets (will be skipped): {len(incomplete_groups)}")
        for base_name, files in incomplete_groups.items():
            clean_name = clean_sample_name(base_name)
            print(f"      {clean_name} ({len(files)} files)")
    
    print(f"\n🚀 Proceeding with automatic processing...")
    return complete_groups, incomplete_groups


def check_datasets(complete_groups):
    """Check if there are complete datasets to process."""
    if not complete_groups:
        print("\n❌ No complete datasets found. Cannot proceed.")
        return False
    
    print(f"\n🔄 Found {len(complete_groups)} complete datasets. Processing automatically...")
    return True


def create_individual_plots(complete_groups, directory, averaged_data):
    """Create individual plot files for each sample using FCS data with TXT conversion."""
    # Find all FCS and TXT files
    fcs_files = list(directory.glob("*.fcs"))
    fcs_filenames = [f.name for f in fcs_files]
    txt_files = list(directory.glob("*.txt"))
    txt_filenames = [f.name for f in txt_files]
    
    print(f"\n📈 Creating individual plots...")
    
    # Create dictionary for easy lookup of averaged data
    avg_data_dict = {data['sample_name']: data for data in averaged_data}
    
    plots_created = 0
    
    for base_name, group_data in sorted(complete_groups.items()):
        print(f"   Creating plot for: {base_name}")
        
        # Collect size data from all 3 replicates using FCS files with TXT conversion
        replicate_histograms = []
        
        for file_data in group_data:
            pdf_filename = file_data['filename'] if isinstance(file_data, dict) else file_data
            fcs_filename = find_matching_fcs(pdf_filename, fcs_filenames)
            txt_filename = find_matching_txt(pdf_filename, txt_filenames)
            
            if fcs_filename and txt_filename:
                # Load FCS data (raw particle sizes)
                fcs_path = directory / fcs_filename
                sizes = load_fcs_data(fcs_path)
                
                # Get conversion factor from TXT file
                txt_path = directory / txt_filename
                base_conversion_factor = get_conversion_factor_from_txt(txt_path)
                
                # Get dilution factor from file_data (extracted from PDF)
                dilution_factor = file_data.get('dilution_factor', 1) if isinstance(file_data, dict) else 1
                
                if sizes is not None and base_conversion_factor is not None:
                    # Filter sizes to our range of interest (10-2000 nm)
                    sizes_filtered = sizes[(sizes >= 10) & (sizes <= 2000)]
                    
                    # Generate histogram counts from FCS data
                    log_bins = np.logspace(np.log10(10), np.log10(2000), 50)
                    counts, _ = np.histogram(sizes_filtered, bins=log_bins)
                    
                    # Convert raw counts to particles/ml
                    bin_concentrations = counts * base_conversion_factor * dilution_factor
                    
                    replicate_histograms.append(bin_concentrations)
        
        if len(replicate_histograms) < 3:
            print(f"     ⚠️  Skipping {base_name}: insufficient data")
            continue
        
        # Create individual plot (7x8 cm)
        fig, ax = plt.subplots(1, 1, figsize=(2.76, 3.15))
        
        # Define log-spaced bins
        log_bins = np.logspace(np.log10(10), np.log10(2000), 50)
        bin_centers = (log_bins[:-1] + log_bins[1:]) / 2
        
        # Prepare histogram data for median calculation
        histogram_data = []
        for bin_concentrations in replicate_histograms:
            histogram_data.append((bin_centers, bin_concentrations))
        
        # Calculate median and SD
        bin_centers = histogram_data[0][0]
        all_counts = np.array([data[1] for data in histogram_data])
        median_counts = np.median(all_counts, axis=0)
        sd_counts = np.std(all_counts, axis=0, ddof=1)
        
        # Plot
        ax.plot(bin_centers, median_counts, color='darkblue', linewidth=1.2, zorder=10)
        ax.fill_between(bin_centers, median_counts - sd_counts, median_counts + sd_counts,
                       alpha=0.4, color='cornflowerblue', zorder=5, linewidth=0, edgecolor='none')
        
        # Format
        ax.set_xscale('log')
        ax.set_xlim(10, 2000)
        ax.set_xticks([10, 100, 1000])
        ax.set_xticklabels(['10', '100', '1000'])
        
        clean_title = clean_sample_name(base_name)
        ax.set_title(f'{clean_title}', fontsize=14, fontweight='normal', pad=15)
        ax.set_xlabel('Diameter (nm)', fontsize=12, fontweight='normal')
        ax.set_ylabel('Particles/mL', fontsize=12, fontweight='normal')
        
        # Add info box
        if base_name in avg_data_dict:
            avg_data = avg_data_dict[base_name]
            median_diameter = avg_data['median_x50']
            concentration = avg_data['original_concentration']
            
            info_text = f"{median_diameter:.1f} nm diameter\n"
            if concentration:
                conc_val = float(concentration)
                info_text += f"{conc_val:.1E} particles/mL"
            
            ax.text(0.95, 0.95, info_text, transform=ax.transAxes, fontsize=10,
                   verticalalignment='top', horizontalalignment='right',
                   bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.8,
                           edgecolor='gray', linewidth=0.5))
        
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        ax.tick_params(axis='both', which='major', labelsize=10, width=0.5, length=4, pad=2)
        
        for spine in ax.spines.values():
            spine.set_linewidth(0.5)
        
        # Create output directory
        output_dir = directory / "NTAwesome Output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save individual plot
        plot_filename = output_dir / f"{make_output_stem(clean_title)}.pdf"
        plt.tight_layout()
        plt.savefig(plot_filename, format='pdf', bbox_inches='tight')
        plt.close()
        
        plots_created += 1
    
    print(f"   ✅ Created {plots_created} individual plots")
    return plots_created


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Process a folder of ZetaView PDF, FCS, and TXT files."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Folder containing ZetaView files, or any file inside that folder.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    configure_console_output()

    # Show splash screen
    show_splash_screen()

    args = parse_args(argv)

    # Get directory from command line or interactive user input
    if args.path:
        directory, status_message = resolve_input_directory(args.path)
        if status_message:
            print(status_message)
        if directory is None:
            return 1
    else:
        directory = get_directory_input()

    # Analyze datasets
    complete_groups, incomplete_groups = analyze_datasets(directory)

    if complete_groups is None:
        return 1

    # Check if we have datasets to process
    if not check_datasets(complete_groups):
        return 1

    # Process the directory automatically (creates both individual and summary plots)
    process_directory_automatic(directory, complete_groups)
    return 0


if __name__ == "__main__":
    sys.exit(main())
