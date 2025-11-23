#!/bin/bash

# Цвета для красоты и читаемости
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

CURRENT_DIR=$(basename "$PWD")

echo -e "${GREEN}=== GITHUB REPO SETUP WIZARD ===${NC}"

# 1. Спрашиваем имя репозитория
echo -e "${YELLOW}[?] Имя репозитория?${NC} (Enter = ${CURRENT_DIR})"
read -r INPUT_NAME
REPO_NAME=${INPUT_NAME:-$CURRENT_DIR}

# 2. Спрашиваем про приватность
echo -e "${YELLOW}[?] Сделать репозиторий ПРИВАТНЫМ?${NC} (y/n, Enter = Yes)"
read -r INPUT_VIS
if [[ "$INPUT_VIS" =~ ^[Nn]$ ]]; then
    VISIBILITY="public"
else
    VISIBILITY="private"
fi

# 3. Описание (опционально)
echo -e "${YELLOW}[?] Описание проекта?${NC} (Enter = пропустить)"
read -r DESCRIPTION

# 4. Проверка .gitignore
if [ ! -f ".gitignore" ]; then
    echo -e "${YELLOW}[?] .gitignore не найден. Создать стандартный (Node/General)?${NC} (y/n, Enter = Yes)"
    read -r CREATE_GITIGNORE
    if [[ ! "$CREATE_GITIGNORE" =~ ^[Nn]$ ]]; then
        echo "node_modules/" > .gitignore
        echo "dist/" >> .gitignore
        echo ".env" >> .gitignore
        echo ".DS_Store" >> .gitignore
        echo ".idea/" >> .gitignore
        echo ".vscode/" >> .gitignore
        echo "*.log" >> .gitignore
        echo -e "${GREEN}✅ .gitignore создан.${NC}"
    else
        echo -e "${RED}⚠️ Пропускаю создание .gitignore. Рискуешь запушить мусор.${NC}"
    fi
else
    echo -e "${GREEN}ℹ️ .gitignore уже на месте.${NC}"
fi

# 5. Git Init & Commit
if [ ! -d ".git" ]; then
    git init -b main
    echo -e "${GREEN}✅ Git инициализирован.${NC}"
fi

# Проверяем статус, чтобы не коммитить пустоту
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}[?] Есть незакоммиченные файлы. Сделать 'git add .' и 'git commit'?${NC} (y/n, Enter = Yes)"
    read -r DO_COMMIT
    if [[ ! "$DO_COMMIT" =~ ^[Nn]$ ]]; then
        git add .
        git commit -m "feat: initial commit"
        echo -e "${GREEN}✅ Закоммичено.${NC}"
    fi
fi

# 6. Финальное подтверждение и пуш
echo -e "\n${GREEN}=== SUMMARY ===${NC}"
echo "Repo Name:   $REPO_NAME"
echo "Visibility:  $VISIBILITY"
echo "Description: $DESCRIPTION"
echo -e "${YELLOW}Создаем репо на GitHub и пушим?${NC} (y/n)"
read -r CONFIRM

if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    # Формируем аргументы
    ARGS="--$VISIBILITY --source=. --remote=origin --push"
    
    if [ -n "$DESCRIPTION" ]; then
        ARGS="$ARGS --description=\"$DESCRIPTION\""
    fi

    # Исполняем. eval нужен для правильной обработки кавычек в description, 
    # но здесь используем массив для безопасности, хотя bash eval проще для демонстрации.
    # Лучше вызовем напрямую gh, подставив переменные.
    
    echo -e "${GREEN}🚀 Полетели...${NC}"
    
    if [ -n "$DESCRIPTION" ]; then
        gh repo create "$REPO_NAME" --"$VISIBILITY" --source=. --remote=origin --push --description "$DESCRIPTION"
    else
        gh repo create "$REPO_NAME" --"$VISIBILITY" --source=. --remote=origin --push
    fi
    
    echo -e "${GREEN}🔥 Готово!${NC}"
else
    echo -e "${RED}❌ Отмена операции.${NC}"
fi
