import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SidebarGlobalSettings } from './SidebarGlobalSettings';
import { useEditorStore } from '@/store/useEditorStore';

describe('SidebarGlobalSettings', () => {
  beforeEach(() => {
    useEditorStore.setState({
      background_url: '',
      global_font_url: '',
      global_font_family: '',
      font_library: [
        { family: "'Cairo', sans-serif", url: 'https://fonts.googleapis.com/css2?family=Cairo&display=swap' },
        { family: "'Jaro', sans-serif", url: 'https://fonts.googleapis.com/css2?family=Jaro&display=swap' },
      ],
    });
  });

  it('renders background input and updates background_url in store', () => {
    render(<SidebarGlobalSettings />);
    const bgInput = screen.getByPlaceholderText(/Image URL/i);
    fireEvent.change(bgInput, { target: { value: 'https://example.com/bg.png' } });
    expect(useEditorStore.getState().background_url).toBe('https://example.com/bg.png');
  });

  it('allows clearing the background url', () => {
    useEditorStore.setState({ background_url: 'https://example.com/bg.png' });
    render(<SidebarGlobalSettings />);
    const clearBtn = screen.getByRole('button', { name: /Clear/i });
    fireEvent.click(clearBtn);
    expect(useEditorStore.getState().background_url).toBe('');
  });

  it('renders font selector and switches active font', () => {
    render(<SidebarGlobalSettings />);
    const select = screen.getByTitle(/Choose active global font/i);
    fireEvent.change(select, { target: { value: "'Cairo', sans-serif" } });
    expect(useEditorStore.getState().global_font_family).toBe("'Cairo', sans-serif");
    expect(useEditorStore.getState().global_font_url).toBe('https://fonts.googleapis.com/css2?family=Cairo&display=swap');
  });

  it('allows selecting font via chip and deleting a font chip', () => {
    render(<SidebarGlobalSettings />);
    const jaroChip = screen.getByRole('button', { name: /^Jaro$/i });
    fireEvent.click(jaroChip);
    expect(useEditorStore.getState().global_font_family).toBe("'Jaro', sans-serif");

    const deleteJaroBtn = screen.getByTitle(/Remove Jaro/i);
    fireEvent.click(deleteJaroBtn);
    expect(useEditorStore.getState().font_library.some((f) => f.family === "'Jaro', sans-serif")).toBe(false);
  });

  it('opens Add Font panel, adds popular preset, and auto-detects family name from Google URL', () => {
    render(<SidebarGlobalSettings />);
    const toggleBtn = screen.getByRole('button', { name: /Add Font/i });
    fireEvent.click(toggleBtn);

    // Preset button
    const oswaldPresetBtn = screen.getByRole('button', { name: /^Oswald/i });
    fireEvent.click(oswaldPresetBtn);
    expect(useEditorStore.getState().global_font_family).toBe("'Oswald', sans-serif");
    expect(useEditorStore.getState().font_library.some((f) => f.family.includes('Oswald'))).toBe(true);

    // Google Font URL detection
    const urlInput = screen.getByPlaceholderText(/Google Font URL/i);
    fireEvent.change(urlInput, { target: { value: 'https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap' } });
    const familyInput = screen.getByPlaceholderText(/Font Family/i) as HTMLInputElement;
    expect(familyInput.value).toBe("'Bebas Neue', sans-serif");

    const saveBtn = screen.getByRole('button', { name: /Save & Apply Font/i });
    fireEvent.click(saveBtn);
    expect(useEditorStore.getState().global_font_family).toBe("'Bebas Neue', sans-serif");
  });
});
