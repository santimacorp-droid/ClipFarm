# Design System — AutoClip

> AutoClip The design standard is unique. Do anything UI/Read here before making visual decisions. 
> Direction: **counter-intuitive specialty / Calm Premium**(Reference Dia Browser). Quiet, precise, lots of whitespace, nearly all monochrome., 
> Use only one restrained blue for highlighting. Intended for "serious content creators," not playful toy or cold tech designs.. 

## Product Context
- **what is it**: Based on AI A video slice desktop tool. Stick BSite/YouTube Link or local video → Automatically generates slices and collections. 
- **who is this for**: Content creator / editor. 
- **Type**: macOS Desktop application(Tauri + React + TypeScript). current use Ant Design, Must be redesigned screen by screen according to this system. 
- **landmark**: Of good style, restrained, professional——Make users feel it's a serious, well-made tool.". 

## Aesthetic Direction
- **Direction**: Calm Premium / Restrict editing feelings. 
- **Decoration level**: minimal(Let typography and whitespace do all the work, no decorative excesses.). 
- **atmosphere / style / character**: Quiet, precise, calm, high-end. Extensive negative space, low information density, hairline dividers.. 
- **Reference**: Dia Browser (diabrowser.com) —— sans+serif Mixed typography, nearly all monochrome, one restrained accent color.. 
- **do not explicitly decline**: Toy contrast colors, full color chip, Purple gradient, neon, 3 Column icon grid, centered clustering, pure black. `#000`. 

## Color

Dual themes (light为主, dark 等价). Accent color.**highly restrained**: Used only for active states, animated elements, links.; All others in single color. 

### Light (default))
```css
--bg:        #F6F5F3;  /* Warm light gray background, not pure white */
--card:      #FFFFFF;
--ink:       #1A1A19;  /* Soft near-black text rather than pure black */
--sub:       #6E6B66;  /* secondary text */
--muted:     #A8A59F;  /* weakened/Placeholder */
--line:      #EBE9E4;  /* Hairline border */
--line-2:    #F0EEEA;  /* weak divider */
--accent:    #2D6BFF;  /* The only emphasis in blue, use restraint with */
--thumb:     #EEECE8;  /* Thumbnail placeholder base */
--cta-bg:    #1A1A19;  /* Primary button: filled ink */
--cta-fg:    #FFFFFF;
```

### Dark mode
```css
--bg:        #19181A;  /* Warm close to black, not pure black */
--card:      #211F22;
--ink:       #ECEAE6;  /* warm white text */
--sub:       #A6A29B;
--muted:     #76726C;
--line:      #2C2A2D;
--line-2:    #232124;
--accent:    #5A8BFF;  /* Blue brightens one level on deep backgrounds */
--thumb:     #262428;
--cta-bg:    #ECEAE6;  /* Primary button: light ink */
--cta-fg:    #19181A;
```

### Semantic colors (common for both themes, restrained usage).)
```css
--ok:    #5BB36A;  /* Completed (small dot)) */
--warn:  #E6B23C;
--error: #E66A5C;  /* Failure */
--info:  var(--accent);
```
- **Dark strategy**: Not inverted light mode, but redefined surface hierarchy.; Emphasize blue brightens about 10–15% Ensure contrast. 

## Typography

sans + serif Mixed typography is the source of sophistication: serifs only for…**Latin brand moment**(wordmark, Large numbers), Chinese and UI Always clean sans-serif. 

- **Brand/Serif (Latin only))**: `Instrument Serif`(Contain italic). for / used for `AutoClip` wordmark, Large fonts for English numerals to make them eye-catching. 
- **Chinese**: `PingFang SC`(mac Native, most restrained) preferred, fallback for cross-platform compatibility. `Noto Sans SC`. 
- **UI / Main text (Latin))**: `Geist`(400/500/600). **unused Inter/Roboto**. 
- **data / number / timestamp**: `Geist Mono`(tabular). 
- **font stack**: 
  ```css
  --font-sans: "Geist", "PingFang SC", "Noto Sans SC", system-ui, sans-serif;
  --font-serif: "Instrument Serif", Georgia, serif;   /* Latin only */
  --font-mono: "Geist Mono", ui-monospace, monospace;
  ```
- **font size tier**(rem, 16px Baseline): 
  | Role | font size | font weight | line height |
  |------|------|------|------|
  | wordmark(serif)| 28px | 400 | 1.1 |
  | Block title h2 | 16px | 600 | 1.3 |
  | Card title | 15px | 500 | 1.45 |
  | body text / main text | 14–15px | 400 | 1.5 |
  | Secondary/metadata | 12.5–13px | 400/500 | 1.4 |
  | Label/uppercase | 11px / letter-spacing .8px | 500 | — |

## Spacing
- **Baseline**: 4px. 
- **density**: spacious(White space much, information less). 
- **Stage**: `2(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(40) 3xl(56)`. 
- **commonly / often / usual**: Inner padding in window 56px; block spacing 56px; card grid gap 24px; Inner padding of cards 20–22px; Large whitespace between import area and first item.. 

## Layout
- **方Form way / method / manner**: grid-disciplined(Restrained grid system, no playful editorial breaking.. 
- **Project grid**: 3 Columns (large spacing, large cards), stacked on narrow screens. 2/1 List. 
- **Maximum content width**: Follow window, left and right 56px safe margins. 
- **Rounded corner**: Card/input field/thumbnail `16px`; small element `10px`; Button/Badge/section switcher `999px`(capsule). 
- **border**: fine hair level `1px solid var(--line)`, On borders instead of overlapping shadows to separate. 

## Components
- **primary button**: Filled ink caps (light background=Black/Dark mode=Light ink), text 14.5px/500, inner padding ~14×26px. 
- **secondary button**: Hairline border caps with text `--sub`. 
- **section switcher**(Link/File): capsule container `--line-2` Base, selected item `--card` Base + ultra-light shadow. 
- **State expression (restraint))**: A small dot in the top-left corner of thumbnails + text label(`downloading`/`analyzing`=accent, `completed`=ok, `Failure`=error). progress meter 4px thin lines(accent), Right percentage used mono. 
- **Successfully obtained metadata**: pure gray mono number + Midpoint separated, e.g. `7 Slice · 1 Collection · 8 months ago`, **No colored chip**. 
- **shadow / shading**: extremely light / very light. `0 1px 2px rgba(0,0,0,.03), 0 8px 24px rgba(0,0,0,.04)`(Deep color reduces opacity accordingly). 

## Motion
- **方Form way / method / manner**: minimal-functional + Individual intentional. Only create meaningful transitions, no showmanship.. 
- **Bounce**: enter / going in / come into `ease-out`, Exit `ease-in`, shift / displacement `ease-in-out`. 
- **Duration**: micro 80–120ms, short 150–250ms. 
- **micro-interaction**: Card hover Move up 2px + ultra-light shadow; Progress line smooth transition. 
- **A worthwhile highlight to implement**: 「Compositing succeeded」Provide restrained but ritualistic transitions (no confetti, no bounces) to support the idea of sharing.". 

## Decisions Log
| Date | decision | reason / cause / rationale |
|------|------|------|
| 2026-05-31 | Initial design system | /design-consultation Evolution of direction (warm editing…→toy-style→Reject) final lock Dia Form「counter-intuitive specialty」, Shallow/Deep dual theme, no main titles, low density, single restrained blue..  |
