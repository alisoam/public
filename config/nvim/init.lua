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
  use {
    "hrsh7th/nvim-cmp",
    requires = {
      { "hrsh7th/cmp-nvim-lsp" },
      { "hrsh7th/cmp-vsnip" },
      { "hrsh7th/vim-vsnip" },
    },
  }
  use {
    "scalameta/nvim-metals",
    requires = {
      "nvim-lua/plenary.nvim",
      "mfussenegger/nvim-dap",
    },
  }
  use 'mfussenegger/nvim-dap'
  use 'mfussenegger/nvim-dap-python'
  use { "rcarriga/nvim-dap-ui", requires = {"mfussenegger/nvim-dap"} }
  use {
    'glacambre/firenvim',
    run = function() vim.fn['firenvim#install'](0) end 
  }
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
  tab = '»·',
}

vim.opt.list = true
vim.cmd([[colorscheme nord]])

vim.g.airline_powerline_fonts = 1
vim.g.airline_theme='base16_nord'

vim.api.nvim_create_autocmd({'UIEnter'}, {
  callback = function(event)
    local client = vim.api.nvim_get_chan_info(vim.v.event.chan).client
    if client ~= nil and client.name == 'Firenvim' then
      vim.o.laststatus = 0
      vim.g.airline_section_c = ''
--      vim.opt.guifont = {'Iosevka', 'h12'}
    else

      vim.g.syntastic_python_python_exec = 'python3'
      vim.g.syntastic_python_checkers = {'flake8', 'pylint', 'mypy', 'python'}
      vim.g.syntastic_python_flake8_post_args = '--ignore=E501'
      vim.python_highlight_all=1
      -- vim.opt.statusline.append('%#warningmsg#')
      -- vim.opt.statusline.append(SyntasticStatuslineFlag())
      -- vim.opt.statusline.append('%*')
      
    --  vim.g.syntastic_always_populate_loc_list = 0 """ 1
    --  vim.g.syntastic_auto_loc_list = 0 """1
      vim.g.syntastic_check_on_open = 1
      vim.g.syntastic_check_on_wq = 1
      -- syntax on
    end
  end
})

vim.api.nvim_command('filetype plugin on')
vim.api.nvim_command('filetype plugin indent on')
vim.g.tex_flavor = 'latex'
vim.api.nvim_command('syntax on')
vim.api.nvim_command('set termbidi')
vim.opt.foldlevel = 0
vim.opt.foldlevelstart = 99
vim.g.tex_fold_enabled = 0
--vim.opt.Tex_FoldedSections = ''
--vim.opt.Tex_FoldedEnvironments = ''
--vim.opt.Tex_FoldedMisc = ''

--[[

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
require 'dap-py'
