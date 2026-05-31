local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.loop.fs_stat(lazypath) then
  vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable", -- latest stable release
    lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

vim.g.mapleader = " " -- Make sure to set `mapleader` before lazy so your mappings are correct
vim.g.maplocalleader = "\\" -- Same for `maplocalleader`

require("lazy").setup({
  {
    'sainnhe/gruvbox-material',
    lazy = false,
    priority = 1000,
    config = function()
      vim.opt.termguicolors = true
      vim.g.gruvbox_material_enable_italic = true
      vim.g.gruvbox_material_background = 'hard'
      vim.g.gruvbox_material_foreground = 'material'
      vim.o.background = 'dark'
      vim.cmd.colorscheme('gruvbox-material')
    end
  },
  {
    "tpope/vim-sleuth",
    event = "BufReadPre",
  },
  {
    "vim-airline/vim-airline",
    lazy = false,
    dependencies = {"vim-airline/vim-airline-themes"},
    config = function()
      vim.g.airline_powerline_fonts = 1
      vim.g.airline_theme = 'base16'
    end,
  },
  {
    "Yggdroot/indentLine",
    lazy = false,
    config = function()
      vim.g.indentLine_leadingSpacChar='.'
      vim.g.indentLine_leadingSpaceEnabled = '1'
      vim.g.indentLine_concealcursor = 'inc'
      vim.g.indentLine_conceallevel = 1
      vim.g.indentLine_char_list = {'|', '¦', '┆', '┊'}
    end,
  },
  "airblade/vim-gitgutter",
  "tpope/vim-fugitive",
  "neovim/nvim-lspconfig",
  -- "posva/vim-vue",,
  {
    "fatih/vim-go",
    ft = "go",
    config = function()
      vim.g.go_def_mode = 'gopls'
      vim.g.go_info_mode = 'gopls'
    end,
  },
  {"rust-lang/rust.vim", ft = "rs"},
  {"hrsh7th/nvim-cmp", dependencies = {"hrsh7th/cmp-nvim-lsp", "hrsh7th/cmp-buffer", "hrsh7th/cmp-vsnip", "hrsh7th/vim-vsnip"}},
  {
    "scalameta/nvim-metals",
    dependencies = {
      "nvim-lua/plenary.nvim",
    },
    ft = { "scala", "sbt", "java" },
    opts = function()
      local metals_config = require("metals").bare_config()
      metals_config.on_attach = function(client, bufnr)
      end
  
      return metals_config
    end,
    config = function(self, metals_config)
      local nvim_metals_group = vim.api.nvim_create_augroup("nvim-metals", { clear = true })
      vim.api.nvim_create_autocmd("FileType", {
        pattern = self.ft,
        callback = function()
          require("metals").initialize_or_attach(metals_config)
        end,
        group = nvim_metals_group,
      })
    end,
  },
  {"mfussenegger/nvim-dap-python", ft = "py", dependencies = {"mfussenegger/nvim-dap"}},
  "github/copilot.vim",
  {
    "carlos-algms/agentic.nvim",
    opts = {
      provider = "opencode-acp",
      acp_providers = {
        ["claude-agent-acp"] = {
          env = {
            ["claude-agent-acp"] = {
              env = {
                TZ = "Asia/Singapore",
              },
            },
          },
        },
      },
    },
    keys = {
      {
        "<C-\\>",
        function() require("agentic").toggle() end,
        mode = { "n", "v", "i" },
        desc = "Toggle Agentic Chat"
      },
      {
        "<C-'>",
        function() require("agentic").add_selection_or_file_to_context() end,
        mode = { "n", "v" },
        desc = "Add file or selection to Agentic to Context"
      },
      {
        "<C-,>",
        function() require("agentic").new_session() end,
        mode = { "n", "v", "i" },
        desc = "New Agentic Session"
      },
      {
        "<A-i>r", -- ai Restore
        function()
            require("agentic").restore_session()
        end,
        desc = "Agentic Restore session",
        silent = true,
        mode = { "n", "v", "i" },
      },
      {
        "<leader>ad", -- ai Diagnostics
        function()
            require("agentic").add_current_line_diagnostics()
        end,
        desc = "Add current line diagnostic to Agentic",
        mode = { "n" },
      },
      {
        "<leader>aD", -- ai all Diagnostics
        function()
            require("agentic").add_buffer_diagnostics()
        end,
        desc = "Add all buffer diagnostics to Agentic",
        mode = { "n" },
      },
    },
  },
  {
    "benlubas/molten-nvim",
    version = "^1.0.0", -- use version <2.0.0 to avoid breaking changes
    -- dependencies = { "3rd/image.nvim" },
    build = ":UpdateRemotePlugins",
    init = function()
      -- these are examples, not defaults. Please see the readme
      --vim.g.molten_image_provider = "image.nvim"
      vim.g.molten_output_win_max_height = 20
    end,
  },
})

vim.opt.autoindent = true
vim.opt.laststatus = 2

vim.opt.number = true
vim.nocompatible = true

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

vim.lsp.config('gopls', {})
vim.lsp.enable('gopls')
vim.lsp.config('pyright', {})
vim.lsp.enable('pyright')
vim.lsp.config('clangd', {})
vim.lsp.enable('clangd')
require 'lsp-cfg'
