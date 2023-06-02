local Plug = vim.fn['plug#']

--[[vim.call('plug#begin', '~/.config/nvim/plugged')

-- Plug 'Valloric/YouCompleteMe'
-- Plugin 'rdnetto/YCM-Generator'
-- Plug 'neoclide/coc.nvim', {'branch': 'release'}
Plug('sakhnik/nvim-gdb', {['do'] = ':!./install.sh | UpdateRemotePlugins'})
Plug 'vim-syntastic/syntastic'
Plug 'nvie/vim-flake8'
Plug 'elixir-editors/vim-elixir'

--Plug('glacambre/firenvim', {
--['do'] = function()
--	firenvim install(0)
--end
--})

Plug 'nvim-lua/plenary.nvim'
Plug 'scalameta/nvim-metals'
Plug 'neovim/nvim-lspconfig'
vim.call('plug#end')
]]

local use = require('packer').use
require('packer').startup(function()
  use 'wbthomason/packer.nvim' -- Package manager
  use 'arcticicestudio/nord-vim'
  use 'airblade/vim-gitgutter'
  use 'Yggdroot/indentLine'
  use 'vim-airline/vim-airline'
  use 'vim-airline/vim-airline-themes'
  use 'posva/vim-vue'
  use 'tpope/vim-fugitive'
  use 'fatih/vim-go'
  use 'rust-lang/rust.vim'
  use 'neovim/nvim-lspconfig'
  use({
    "hrsh7th/nvim-cmp",
    requires = {
      { "hrsh7th/cmp-nvim-lsp" },
      { "hrsh7th/cmp-vsnip" },
      { "hrsh7th/vim-vsnip" },
    },
  })
  use({
    "scalameta/nvim-metals",
    requires = {
      "nvim-lua/plenary.nvim",
      "mfussenegger/nvim-dap",
    },
  })
end)

vim.opt.autoindent = true
vim.opt.laststatus = 2

vim.opt.number = true
vim.nocompatible = true

vim.g.indentLine_leadingSpacChar='.'
vim.g.indentLine_leadingSpaceEnabled = '1'
vim.g.indentLine_concealcursor = 'inc'
vim.g.indentLine_conceallevel = 1
vim.g.indentLine_char_list = {'|', '¦', '┆', '┊'}
vim.g.nord_underline = 1
vim.g.nord_italic_comments = 1
vim.g.nord_uniform_status_lines = 1
vim.g.nord_cursor_line_number_background = 1
vim.g.nord_uniform_diff_background = 1


vim.opt.number = true
vim.opt.cursorline = true
vim.opt.listchars = {
  nbsp = '␣',
  eol = '⤶',
  trail = '.',
  extends = '◀',
  precedes = '▶',
  -- tab = '»',
}
---{tab = '', nbsp = '␣', trail = '.', eol = '¬', precedes = '«', extends = '»'}

vim.opt.list = true
vim.cmd([[colorscheme nord]])

vim.g.airline_powerline_fonts = 1
vim.g.airline_theme='base16_nord'
--[[
filetype plugin on
filetype plugin indent on

set termbidi

if exists('g:started_by_firenvim')
  let g:airline_section_c = ''
endif
if exists('g:started_by_firenvim')
else
  let g:syntastic_python_python_exec = 'python3'
  let g:syntastic_python_checkers = ['flake8', 'pylint', 'mypy', 'python']
  let g:syntastic_python_flake8_post_args='--ignore=E501'
  let python_highlight_all=1
  set statusline+=%#warningmsg#
  set statusline+=%{SyntasticStatuslineFlag()}
  set statusline+=%*
  
  let g:syntastic_always_populate_loc_list = 0 """ 1
  let g:syntastic_auto_loc_list = 0 """1
  let g:syntastic_check_on_open = 1
  let g:syntastic_check_on_wq = 1
  syntax on
endif

"let g:flake8_show_quickfix=0
"let g:flake8_show_in_file=1
"let g:flake8_show_in_gutter=1
"
"
function! NvimGdbNoTKeymaps()
  tnoremap <silent> <buffer> <esc> <c-\><c-n>
endfunction

let g:nvimgdb_config_override = {
  \ 'key_next': 'n',
  \ 'key_step': 's',
  \ 'key_finish': 'f',
  \ 'key_continue': 'c',
  \ 'key_until': 'u',
  \ 'key_breakpoint': 'b',
  \ 'set_tkeymaps': "NvimGdbNoTKeymaps",
  \ }

vim.g.tex_flavor = "latex"
]]

vim.opt.conceallevel = 2
vim.opt.exrc = true
vim.opt.secure = true

--vim.api.nvim_set_keymap("n", '<C-c>', '"+c', { silent = true })
--vim.api.nvim_set_keymap("n", '<C-y>', '"+y', { silent = true })
--vim.api.nvim_set_keymap("n", '<C-p>', '"+p', { silent = true })

require 'lspconfig'
require 'lspconfig'.pyright.setup{}
require 'lsp-cfg'
