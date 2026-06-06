import socket
import threading
from game_logic import (
    Player, initialize_game, save_game, load_game,
    get_log, play_card, deck, current_player,
    next_turn, is_valid_play, check_victory, sync_all_clients
)

HOST = '192.168.100.29'
PORT = 12345
MIN_PLAYERS = 3

clients = []

def handle_client(conn, addr):
    try:
        conn.sendall("Enter your name: ".encode())
        name = conn.recv(1024).decode().strip()

        if any(p.name == name for p in clients):
            conn.sendall("Name already taken.\n".encode())
            conn.close()
            return

        player = Player(name, conn)
        clients.append(player)
        print(f"{name} joined from {addr}")
        conn.sendall("Waiting for other players...\n".encode())

        if len(clients) == MAX_PLAYERS:
            conn.sendall("You are the host. How many cards per player? ".encode())
            cards_msg = conn.recv(1024).decode().strip()
            try:
                cards_per_player = int(cards_msg)
            except:
                cards_per_player = 3

            initialize_game(clients, cards_per_player)
            sync_all_clients()

        while True:
            msg = conn.recv(1024).decode().strip()
            if not msg:
                break

            if current_player() != player:
                conn.sendall("Not your turn!\n".encode())
                continue

            if msg.startswith("/play"):
                try:
                    indices = [int(x)-1 for x in msg.split()[1:]]
                    selected_cards = [player.hand[i] for i in indices if 0 <= i < len(player.hand)]

                    if not selected_cards:
                        conn.sendall("Invalid card indices.\n".encode())
                        continue

                    # Validate and play each card
                    if all(is_valid_play(card, current_player().hand[0]) for card in selected_cards):
                        for card in selected_cards:
                            if not play_card(player, [card]):  # Pass as list
                                conn.sendall("Invalid move.\n".encode())
                                break
                        else:
                            winner = check_victory()
                            if winner:
                                for p in clients:
                                    p.conn.sendall(f"{winner} wins!\n".encode())
                            else:
                                next_turn()
                        sync_all_clients()
                    else:
                        conn.sendall("Invalid play.\n".encode())

                except Exception as e:
                    conn.sendall(f"Error: {e}\n".encode())

            elif msg.startswith("/draw"):
                card = player.draw_card(deck)
                conn.sendall(f"You drew: {card}\n".encode())
                next_turn()
                sync_all_clients()

            elif msg.startswith("/save"):
                save_game()
                conn.sendall("Game saved.\n".encode())

            elif msg.startswith("/load"):
                if load_game([p.conn for p in clients]):
                    conn.sendall("Game loaded.\n".encode())
                    sync_all_clients()
                else:
                    conn.sendall("No save found.\n".encode())

            elif msg.startswith("/log"):
                conn.sendall(get_log().encode())

            else:
                conn.sendall("Unknown command.\n".encode())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()

    print(f"Server started on {HOST}:{PORT}")

    while len(clients) < MAX_PLAYERS:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()
